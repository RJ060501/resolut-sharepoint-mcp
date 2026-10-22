import io
import zipfile
from dataclasses import replace

import pytest
from pypdf import PdfWriter

from resolut_mcp.errors import ConnectorError
from resolut_mcp.extraction import extract_document


@pytest.mark.parametrize("name,expected",[
    ("approved_hvac.txt","HVAC"),
    ("synthetic_hvac.docx","HVAC"),
    ("commissioning.pdf","commissioning"),
])
async def test_supported_files_extracted_in_disposable_process(settings,name,expected):
    result = await extract_document((settings.fixtures_path/name).read_bytes(),name,settings)
    assert expected.casefold() in result["text"].casefold()
    assert result["content_is_untrusted"] is True


async def test_utf16_bom(settings):
    r = await extract_document("approved UTF16".encode("utf-16"),"file.txt",settings)
    assert "UTF16" in r["text"]


async def test_unsupported_extension(settings):
    with pytest.raises(ConnectorError) as e: await extract_document(b"x","model.rvt",settings)
    assert e.value.code == "unsupported_format"


async def test_file_size_limit(settings):
    with pytest.raises(ConnectorError) as e:
        await extract_document(b"x"*101,"file.txt",replace(settings,max_file_bytes=100))
    assert e.value.code == "file_too_large"


async def test_text_output_limit_is_not_silent(settings):
    with pytest.raises(ConnectorError) as e:
        await extract_document(b"x"*101,"file.txt",replace(settings,max_text_chars=100))
    assert e.value.code == "extraction_limit"


async def test_empty_image_only_pdf_reported(settings):
    output=io.BytesIO(); w=PdfWriter(); w.add_blank_page(width=100,height=100); w.write(output)
    with pytest.raises(ConnectorError) as e: await extract_document(output.getvalue(),"scan.pdf",settings)
    assert e.value.code == "no_extractable_text"


async def test_encrypted_pdf_reported(settings):
    output=io.BytesIO(); w=PdfWriter(); w.add_blank_page(width=100,height=100); w.encrypt("synthetic-password"); w.write(output)
    with pytest.raises(ConnectorError) as e: await extract_document(output.getvalue(),"file.pdf",settings)
    assert e.value.code == "encrypted_file"


async def test_pdf_page_limit(settings):
    output=io.BytesIO(); w=PdfWriter()
    for _ in range(3): w.add_blank_page(width=100,height=100)
    w.write(output)
    with pytest.raises(ConnectorError) as e:
        await extract_document(output.getvalue(),"file.pdf",replace(settings,max_pdf_pages=2))
    assert e.value.code == "extraction_limit"


@pytest.mark.parametrize("name,data",[("file.pdf",b"not pdf"),("file.docx",b"not docx"),("file.txt",b"\x00binary")])
async def test_malformed_files_do_not_echo_parser_errors(settings,name,data):
    with pytest.raises(ConnectorError) as e: await extract_document(data,name,settings)
    assert e.value.code in {"extraction_failed","no_extractable_text"}


async def test_xml_entities_rejected(settings):
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w") as z:
        z.writestr("word/document.xml",'<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><x>&y;</x>')
    with pytest.raises(ConnectorError) as e: await extract_document(output.getvalue(),"file.docx",settings)
    assert e.value.code == "extraction_failed"
