import time

import pytest
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.core.file_storage import DatabaseStorage, LinkExpired, read_link
from apps.core.models import StoredFile
from apps.students.models import StudentResume

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_storage_round_trip():
    storage = DatabaseStorage()
    name = storage.save("resumes/1/2/a.pdf", ContentFile(PDF))
    assert storage.exists(name) and storage.size(name) == len(PDF)
    with storage.open(name) as f:
        assert f.read() == PDF
    second = storage.save("resumes/1/2/a.pdf", ContentFile(b"%PDF-other"))
    assert second != name  # an existing name is never overwritten
    storage.delete(name)
    assert not storage.exists(name) and storage.exists(second)
    with pytest.raises(FileNotFoundError):
        storage.open(name)


def test_link_carries_its_own_expiry_and_cannot_be_forged():
    storage = DatabaseStorage()
    url = storage.signed_url("resumes/x.pdf", expires=60, content_type="application/pdf")
    token = url.removeprefix("/api/v1/files/").removesuffix("/")
    assert read_link(token) == ("resumes/x.pdf", "application/pdf")
    with pytest.raises(LinkExpired):
        read_link(token, now=time.time() + 61)
    with pytest.raises(signing.BadSignature):
        read_link(token[:-2] + ("AA" if not token.endswith("AA") else "BB"))


def _link(content=PDF, content_type="application/pdf", expires=300):
    storage = DatabaseStorage()
    name = storage.save("certificates/1/1/file.bin", ContentFile(content))
    return name, storage.signed_url(name, expires=expires, content_type=content_type)


def test_link_serves_the_file_sandboxed_and_frameable_only_by_the_app():
    _, url = _link()
    response = APIClient().get(url)  # no session: the signed link is the authorization
    assert response.status_code == 200
    assert response.content == PDF
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == "inline"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == "sandbox"
    assert response["X-Frame-Options"] == "SAMEORIGIN"
    assert "no-store" in response["Cache-Control"]


def test_tampered_expired_and_deleted_links_are_refused(monkeypatch):
    name, url = _link(expires=5)
    assert APIClient().get(url[:-3] + "xx/").status_code == 403
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 10)
    assert APIClient().get(url).status_code == 403
    monkeypatch.setattr(time, "time", real)
    StoredFile.objects.filter(name=name).delete()
    assert APIClient().get(url).status_code == 404


def test_resume_upload_view_and_history_cleanup_through_the_api(make_student, as_user):
    student = make_student()
    client = as_user(student.user)

    def upload(n):
        response = client.post(
            "/api/v1/students/me/resume/",
            {"file": SimpleUploadedFile(f"cv{n}.pdf", PDF + str(n).encode(), "application/pdf")},
            format="multipart",
        )
        assert response.status_code == 201, response.content

    upload(1)
    link = client.get("/api/v1/students/me/resume/").json()["url"]
    assert link.startswith("/api/v1/files/")
    assert APIClient().get(link).content == PDF + b"1"
    for n in range(2, 6):
        upload(n)
    # Only the kept versions' bytes remain in the database (KEEP_RESUME_VERSIONS = 3).
    kept = set(StudentResume.objects.filter(student=student).values_list("file", flat=True))
    assert len(kept) == 3
    assert set(StoredFile.objects.values_list("name", flat=True)) == kept


def test_certificate_image_is_served_with_its_detected_type(make_student, as_user):
    client = as_user(make_student().user)
    item = client.post("/api/v1/evidence/", {"source_type": "certification", "title": "AWS"}, format="json").json()
    response = client.post(
        f"/api/v1/evidence/{item['id']}/certificate/",
        {"file": SimpleUploadedFile("cert.png", PNG, "application/pdf")},  # declared type is ignored
        format="multipart",
    )
    assert response.status_code == 201, response.content
    link = client.get(f"/api/v1/evidence/{item['id']}/certificate/").json()["url"]
    served = APIClient().get(link)
    assert served.status_code == 200 and served["Content-Type"] == "image/png" and served.content == PNG
