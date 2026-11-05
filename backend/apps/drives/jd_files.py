"""Text extraction for uploaded job descriptions (PDF, DOCX, TXT). The file itself is not stored:
its text becomes the drive's job description and goes through the same deterministic JD processing
as pasted text, so the officer can read and correct what was extracted.

Uploads are untrusted, so size, page count, decompressed size and text length are all capped, and
the type is decided by the file's magic bytes rather than its name or declared content type.
Scanned (image-only) PDFs have no text layer; there is no OCR, so those are rejected with a hint
to paste the text instead.
"""

import io
import re
import zipfile
from xml.etree import ElementTree

from django.conf import settings

MAX_PDF_PAGES = 30
MAX_DOCX_XML_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 50_000
ALLOWED_SUFFIXES = (".pdf", ".docx", ".txt")
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class JDFileError(ValueError):
    pass


def extract_jd_text(uploaded):
    max_bytes = getattr(settings, "JD_MAX_BYTES", 5 * 1024 * 1024)
    if uploaded.size > max_bytes:
        raise JDFileError(f"The JD file must be {max_bytes // (1024 * 1024)} MB or smaller.")
    name = (uploaded.name or "").lower()
    if not name.endswith(ALLOWED_SUFFIXES):
        raise JDFileError("Upload the JD as a PDF, Word (.docx) or plain-text (.txt) file.")
    uploaded.seek(0)
    data = uploaded.read()
    if data.startswith(b"%PDF-"):
        text = _pdf_text(data)
    elif data.startswith(b"PK\x03\x04"):
        text = _docx_text(data)
    elif name.endswith(".txt"):
        text = _plain_text(data)
    else:
        raise JDFileError("That file is not a valid PDF, Word (.docx) or text file.")
    text = _tidy(text)
    if not text:
        raise JDFileError(
            "No text could be read from that file. If it is a scanned document, paste the JD text instead."
        )
    if len(text) > MAX_TEXT_CHARS:
        raise JDFileError(f"The JD text is longer than {MAX_TEXT_CHARS:,} characters. Paste the relevant part instead.")
    return text


def _pdf_text(data):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise JDFileError("That PDF is password-protected. Upload an unprotected copy or paste the text.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise JDFileError(f"That PDF has more than {MAX_PDF_PAGES} pages; a JD should be much shorter.")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except JDFileError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise JDFileError("That PDF could not be read.") from exc


def _docx_text(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            try:
                info = archive.getinfo("word/document.xml")
            except KeyError as exc:
                raise JDFileError("That file is not a Word (.docx) document.") from exc
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise JDFileError("That Word document is too large to read.")
            xml = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise JDFileError("That Word document could not be read.") from exc
    try:
        root = ElementTree.fromstring(xml)  # noqa: S314 - bundled expat (>= 2.4.1) limits entity expansion
    except ElementTree.ParseError as exc:
        raise JDFileError("That Word document could not be read.") from exc
    paragraphs = []
    for para in root.iter(f"{WORD_NS}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{WORD_NS}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{WORD_NS}tab":
                parts.append("\t")
            elif node.tag in (f"{WORD_NS}br", f"{WORD_NS}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def _plain_text(data):
    if b"\x00" in data:
        raise JDFileError("That file is not a plain-text file.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _tidy(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t ]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
