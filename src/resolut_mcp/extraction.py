from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path, PurePath
from typing import Any

from .config import Settings
from .errors import ConnectorError
from .extract_worker import supported


async def extract_document(data: bytes, filename: str, settings: Settings) -> dict[str, Any]:
    if not supported(filename):
        raise ConnectorError("unsupported_format")
    if len(data) > settings.max_file_bytes:
        raise ConnectorError("file_too_large")
    # The worker never receives the API secret, Graph token, or incoming token.
    environment = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "LANG", "LC_ALL", "TEMP", "TMP") if k in os.environ}
    environment.update({"PYTHONPATH": str(Path(__file__).resolve().parent.parent),
                        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "resolut_mcp.extract_worker", PurePath(filename).suffix.casefold(),
        str(settings.max_text_chars), str(settings.max_pdf_pages), str(settings.max_file_bytes),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env=environment,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(data), timeout=settings.extraction_seconds)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.wait()
        if asyncio.current_task() and asyncio.current_task().cancelling():
            raise
        raise ConnectorError("extraction_limit") from None
    if process.returncode != 0 or len(output) > settings.max_text_chars*7 + 16384:
        raise ConnectorError("extraction_limit")
    try:
        result = json.loads(output)
        if not result["ok"]:
            raise ConnectorError(result["code"])
        return result["document"]
    except (ValueError, KeyError, TypeError):
        raise ConnectorError("extraction_failed") from None
