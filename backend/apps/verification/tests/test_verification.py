import pytest

from apps.accounts.roles import Role
from apps.core.models import AuditLog, ImmutableRecordError
from apps.evidence.models import SourceType, VerificationStatus
from apps.taxonomy.models import Level
from apps.verification.models import Verification

pytestmark = pytest.mark.django_db
QUEUE = "/api/v1/verification/queue/"


@pytest.fixture
def pending(make_student, taxonomy, give_evidence):
    from apps.evidence.services import request_verification

    alice = make_student(name="Alice")
    item = give_evidence(alice, SourceType.PROJECT, "Shop backend", [(taxonomy("Django"), Level.INTERMEDIATE)])
    request_verification(item)
    return item


def decide(client, item, decision, comment=""):
    return client.post(
        f"/api/v1/verification/{item.pk}/decide/", {"decision": decision, "comment": comment}, format="json"
    )


def test_mentor_sees_queue_and_verifies(pending, faculty, as_user):
    client = as_user(faculty)
    assert [e["id"] for e in client.get(QUEUE).json()] == [pending.pk]
    response = decide(client, pending, "verified", "Reviewed the repository.")
    assert response.status_code == 200
    pending.refresh_from_db()
    assert pending.verification_status == VerificationStatus.VERIFIED
    assert Verification.objects.get(evidence=pending).reviewer == faculty
    assert AuditLog.objects.filter(action="evidence.verified").exists()
    assert pending.student.user.notifications.filter(kind="verification_completed").exists()
    assert client.get(QUEUE).json() == []


def test_rejection_requires_a_reason(pending, faculty, as_user):
    client = as_user(faculty)
    assert decide(client, pending, "rejected").status_code == 400
    assert decide(client, pending, "rejected", "Repository is private.").status_code == 200
    pending.refresh_from_db()
    assert pending.verification_status == VerificationStatus.REJECTED


def test_non_mentor_faculty_cannot_verify(pending, make_user, as_user):
    other = make_user(email="other@example.test", roles=[Role.FACULTY])
    assert decide(as_user(other), pending, "verified").status_code == 404
    assert as_user(other).get(QUEUE).json() == []


def test_student_cannot_verify_own_evidence(pending, as_user):
    assert decide(as_user(pending.student.user), pending, "verified").status_code == 403


def test_officer_is_not_a_verifier(pending, officer, as_user):
    assert decide(as_user(officer), pending, "verified").status_code == 403


def test_only_pending_evidence_can_be_decided(pending, faculty, as_user):
    client = as_user(faculty)
    decide(client, pending, "verified")
    assert decide(client, pending, "rejected", "changed my mind").status_code == 400


def test_verification_records_are_immutable(pending, faculty, as_user):
    decide(as_user(faculty), pending, "verified")
    record = Verification.objects.get()
    with pytest.raises(ImmutableRecordError):
        record.delete()
