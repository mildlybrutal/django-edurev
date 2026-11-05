import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.drives.jd_files import JDFileError, extract_jd_text
from apps.drives.models import JDStatus

pytestmark = pytest.mark.django_db

DRIVES = "/api/v1/drives/"
LINES = [
    "Backend Engineer - Synthetic Corp",
    "Must have strong Python and Django skills and experience with PostgreSQL.",
    "Eligibility: minimum 7.5 CGPA, no active backlogs.",
]


def make_pdf(lines):
    """A minimal valid one-page PDF with a text layer (Helvetica, one line per entry)."""
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    ops = "BT /F1 11 Tf 14 TL 72 720 Td " + " ".join(f"({t}) Tj T*" for t in escaped) + " ET"
    stream = ops.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def make_docx(paragraphs, extra_files=None):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", xml)
        for name, content in (extra_files or {}).items():
            archive.writestr(name, content)
    return buf.getvalue()


def upload(name, content):
    return SimpleUploadedFile(name, content)


def test_pdf_text_is_extracted():
    text = extract_jd_text(upload("jd.pdf", make_pdf(LINES)))
    for line in LINES:
        assert line in text


def test_docx_paragraphs_become_lines():
    text = extract_jd_text(upload("JD.DOCX", make_docx(LINES)))
    assert text.splitlines() == LINES


def test_plain_text_is_tidied():
    text = extract_jd_text(upload("jd.txt", "﻿Line one   \r\n\r\n\r\n\r\nLine two\r\n".encode()))
    assert text == "Line one\n\nLine two"


@pytest.mark.parametrize(
    "name,content,message",
    [
        ("jd.exe", b"%PDF-1.4", "PDF, Word"),
        ("jd.pdf", b"MZ\x90\x00 not really a pdf", "not a valid"),  # name says PDF, bytes do not
        ("jd.docx", b"PK\x03\x04garbage", "could not be read"),
        ("jd.txt", b"binary\x00data", "not a plain-text"),
        ("jd.pdf", b"%PDF-1.4\n%%EOF", "could not be read"),  # truncated
        ("jd.pdf", make_pdf([]), "scanned document"),  # a page with no text layer, like a scan
    ],
)
def test_bad_files_are_rejected_with_a_reason(name, content, message):
    with pytest.raises(JDFileError, match=message):
        extract_jd_text(upload(name, content))


def test_docx_without_document_part_is_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("hello.txt", "not a word file")
    with pytest.raises(JDFileError, match="not a Word"):
        extract_jd_text(upload("jd.docx", buf.getvalue()))


def test_size_limit(settings):
    settings.JD_MAX_BYTES = 1024
    with pytest.raises(JDFileError, match="1 MB or smaller|0 MB or smaller"):
        extract_jd_text(upload("jd.txt", b"a" * 2048))


def test_officer_uploads_jd_file_and_it_is_processed(
    make_drive, taxonomy, departments, officer, as_user, django_capture_on_commit_callbacks
):
    drive = make_drive(publish=False)
    client = as_user(officer)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"{DRIVES}{drive.pk}/jd/", {"file": upload("groww-jd.pdf", make_pdf(LINES))}, format="multipart"
        )
    assert response.status_code == 202, response.content
    assert "Django" in response.json()["text"]
    body = client.get(f"{DRIVES}{drive.pk}/jd/").json()
    assert body["status"] == JDStatus.READY
    assert {"Python", "Django", "PostgreSQL"} <= {s["skill"] for s in body["extraction"]["skills"]}
    assert {r["rule_type"] for r in body["extraction"]["eligibility"]} >= {"min_cgpa", "max_active_backlogs"}


def test_jd_upload_needs_exactly_one_input_and_a_readable_file(make_drive, officer, as_user):
    drive = make_drive(publish=False)
    client = as_user(officer)
    assert client.post(f"{DRIVES}{drive.pk}/jd/", {}, format="multipart").status_code == 400
    both = client.post(
        f"{DRIVES}{drive.pk}/jd/", {"text": "Python", "file": upload("jd.txt", b"Python")}, format="multipart"
    )
    assert both.status_code == 400
    bad = client.post(f"{DRIVES}{drive.pk}/jd/", {"file": upload("jd.pdf", b"not a pdf")}, format="multipart")
    assert bad.status_code == 400 and "not a valid" in bad.json()["detail"]
    drive.refresh_from_db()
    assert drive.jd_status == JDStatus.NONE


def test_students_cannot_upload_a_jd(make_drive, make_student, as_user):
    drive = make_drive(publish=False)
    student = make_student()
    response = as_user(student.user).post(
        f"{DRIVES}{drive.pk}/jd/", {"file": upload("jd.txt", b"Python")}, format="multipart"
    )
    assert response.status_code in (403, 404)
