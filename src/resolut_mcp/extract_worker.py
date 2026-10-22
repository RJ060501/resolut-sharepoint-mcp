"""Disposable parser process. Input/output are pipes, not persistent document files."""
from __future__ import annotations

import io
import json
import logging
import sys
import zipfile
from pathlib import PurePath
from typing import Any

from .errors import ConnectorError


def supported(name: str) -> bool:
    return PurePath(name).suffix.casefold() in {".txt", ".docx", ".pdf"}


def extract_bytes(data: bytes, suffix: str, max_chars: int, max_pages: int) -> dict[str, Any]:
    warnings: list[str] = []
    pages = None
    try:
        if suffix == ".txt":
            encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            text = data.decode(encoding, errors="strict")
            if "\x00" in text or any(ord(ch) < 9 for ch in text):
                raise ConnectorError("extraction_failed")
        elif suffix == ".docx":
            if data[:8] == bytes.fromhex("D0CF11E0A1B11AE1"):
                raise ConnectorError("encrypted_file")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if (len(entries) > 2000 or sum(x.file_size for x in entries) > 40*1024*1024
                        or any(x.file_size > 10*1024*1024 or x.file_size > max(1, x.compress_size)*250 for x in entries)):
                    raise ConnectorError("extraction_limit")
                if "word/document.xml" not in archive.namelist():
                    raise ConnectorError("extraction_failed")
                for entry in entries:
                    if entry.flag_bits & 1:
                        raise ConnectorError("encrypted_file")
                    if entry.filename.endswith((".xml", ".rels")):
                        xml = archive.read(entry).upper()
                        if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                            raise ConnectorError("extraction_failed")
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            document = Document(io.BytesIO(data))
            parts = []
            total = 0
            def append(value: str) -> None:
                nonlocal total
                total += len(value) + 1
                if total > max_chars:
                    raise ConnectorError("extraction_limit")
                parts.append(value)
            for block in document.iter_inner_content():
                if isinstance(block, Paragraph):
                    append(block.text)
                elif isinstance(block, Table):
                    for row in block.rows:
                        append(" | ".join(cell.text for cell in row.cells))
            seen: set[str] = set()
            for section in document.sections:
                for area in (section.header, section.footer):
                    value = "\n".join(p.text for p in area.paragraphs)
                    if value.strip() and value not in seen:
                        append(value)
                        seen.add(value)
            text = "\n".join(parts)
            warnings.append("DOCX: body paragraphs/tables and paragraph headers/footers only; drawings, text boxes, revisions, footnotes and embedded files are not interpreted. Verify against the source.")
        elif suffix == ".pdf":
            if not data.lstrip().startswith(b"%PDF-"):
                raise ConnectorError("extraction_failed")
            from pypdf import PdfReader
            logging.getLogger("pypdf").setLevel(logging.CRITICAL)
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise ConnectorError("encrypted_file")
            pages = len(reader.pages)
            if pages > max_pages:
                raise ConnectorError("extraction_limit")
            parts = []
            total = 0
            empty = 0
            for index, page in enumerate(reader.pages, 1):
                value = page.extract_text() or ""
                if not value.strip():
                    empty += 1
                else:
                    part = f"[Page {index}]\n{value}"
                    total += len(part) + 1
                    if total > max_chars:
                        raise ConnectorError("extraction_limit")
                    parts.append(part)
            text = "\n\n".join(parts)
            if empty:
                warnings.append(f"{empty} of {pages} PDF pages have no extractable text; they may be blank or image-only. No OCR was performed.")
            warnings.append("PDF text order and tables may differ from visual layout; images and drawing geometry are not interpreted.")
        else:
            raise ConnectorError("unsupported_format")
        if not text.strip():
            raise ConnectorError("no_extractable_text")
        if len(text) > max_chars:
            raise ConnectorError("extraction_limit")
        return {"text": text, "format": suffix.lstrip("."), "pages": pages, "warnings": warnings,
                "content_is_untrusted": True}
    except ConnectorError:
        raise
    except MemoryError:
        raise ConnectorError("extraction_limit") from None
    except Exception:
        raise ConnectorError("extraction_failed") from None


def main() -> None:
    # Linux production uses both these per-parser limits and systemd process limits.
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    suffix, max_chars, max_pages, max_bytes = sys.argv[1:]
    data = sys.stdin.buffer.read(int(max_bytes) + 1)
    try:
        if len(data) > int(max_bytes):
            raise ConnectorError("file_too_large")
        result = {"ok": True, "document": extract_bytes(data, suffix, int(max_chars), int(max_pages))}
    except ConnectorError as exc:
        result = {"ok": False, "code": exc.code}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
