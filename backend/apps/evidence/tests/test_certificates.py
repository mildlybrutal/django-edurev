import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.accounts.roles import Role
from apps.core.models import AuditLog
from apps.evidence.models import EvidenceFile, VerificationStatus

pytestmark = pytest.mark.django_db
EVIDENCE = "/api/v1/evidence/"
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def owner(make_student):
    return make_student(name="Owner")


def certification(client, title="AWS CCP", source_type="certification"):
    response = client.post(EVIDENCE, {"source_type": source_type, "title": title}, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def upload(client, evidence_id, content=PDF, name="cert.pdf"):
    return client.post(
        f"{EVIDENCE}{evidence_id}/certificate/",
        {"file": SimpleUploadedFile(name, content, "application/octet-stream")},
        format="multipart",
    )


def test_student_uploads_certificate_and_type_comes_from_content(owner, as_user):
    client = as_user(owner.user)
    item = certification(client)
    response = upload(client, item["id"], PNG, "cert.png")
    assert response.status_code == 201, response.content
    assert response.json()["certificate"]["content_type"] == "image/png"
    link = client.get(f"{EVIDENCE}{item['id']}/certificate/").json()
    assert link["url"] and link["content_type"] == "image/png"


def test_certificate_validation(owner, as_user):
    client = as_user(owner.user)
    item = certification(client)
    assert upload(client, item["id"], b"not a pdf at all", "cert.pdf").status_code == 400
    assert upload(client, item["id"], PDF, "cert.exe").status_code == 400
    with override_settings(CERTIFICATE_MAX_BYTES=10):
        assert upload(client, item["id"]).status_code == 400
    project = certification(client, "Repo", source_type="project")
    assert upload(client, project["id"]).status_code == 400
    assert not EvidenceFile.objects.exists()


def test_replacing_keeps_one_file(owner, as_user):
    client = as_user(owner.user)
    item = certification(client)
    upload(client, item["id"])
    upload(client, item["id"], PNG, "v2.png")
    assert EvidenceFile.objects.filter(evidence_id=item["id"]).count() == 1
    assert EvidenceFile.objects.get(evidence_id=item["id"]).original_name == "v2.png"


def test_certificate_visible_to_mentor_and_cell_not_other_students(
    owner, make_student, faculty, officer, make_user, as_user
):
    item = certification(as_user(owner.user))
    upload(as_user(owner.user), item["id"])
    url = f"{EVIDENCE}{item['id']}/certificate/"
    assert as_user(faculty).get(url).status_code == 200
    assert as_user(officer).get(url).status_code == 200
    assert as_user(make_student(name="Other").user).get(url).status_code == 404
    other_faculty = make_user(email="f2@example.test", roles=[Role.FACULTY])
    assert as_user(other_faculty).get(url).status_code == 404
    assert AuditLog.objects.filter(action="evidence.certificate.view").count() == 2
    # Staff can view but never replace or remove a student's certificate.
    assert upload(as_user(faculty), item["id"]).status_code == 403
    assert as_user(officer).delete(url).status_code == 403


def test_certificate_locked_while_pending_and_reopens_after_rejection(owner, as_user):
    from apps.evidence import services

    client = as_user(owner.user)
    item = certification(client)
    upload(client, item["id"])
    evidence = EvidenceFile.objects.get(evidence_id=item["id"]).evidence
    services.set_status(evidence, VerificationStatus.PENDING)
    assert upload(client, item["id"], PNG, "swap.png").status_code == 400
    assert client.delete(f"{EVIDENCE}{item['id']}/certificate/").status_code == 400

    services.set_status(evidence, VerificationStatus.REJECTED)
    assert upload(client, item["id"], PNG, "fixed.png").status_code == 201
    evidence.refresh_from_db()
    assert evidence.verification_status == VerificationStatus.SELF_REPORTED


def test_deleting_evidence_removes_certificate(owner, as_user):
    client = as_user(owner.user)
    item = certification(client)
    upload(client, item["id"])
    assert client.delete(f"{EVIDENCE}{item['id']}/").status_code == 204
    assert not EvidenceFile.objects.exists()
