import pytest

from apps.evidence import services
from apps.evidence.models import EvidenceItem, SourceType, VerificationStatus
from apps.evidence.services import EvidenceError
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
EVIDENCE = "/api/v1/evidence/"


@pytest.fixture
def alice(make_student):
    return make_student(name="Alice")


def test_student_submits_evidence_with_skill_tags(alice, taxonomy, as_user):
    response = as_user(alice.user).post(
        EVIDENCE,
        {
            "source_type": "project",
            "title": "Library API",
            "source_url": "https://example.test/repo",
            "tags": [{"skill_id": taxonomy("Django").pk, "claimed_level": 2}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["verification_status"] == "self_reported"
    assert body["skill_tags"][0]["skill"] == "Django"


def test_student_cannot_self_verify_by_payload(alice, taxonomy, as_user):
    response = as_user(alice.user).post(
        EVIDENCE, {"source_type": "project", "title": "X", "verification_status": "verified"}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == "self_reported"


@pytest.mark.parametrize("source", ["academic", "assessment", "mock_interview"])
def test_students_cannot_submit_institutional_evidence(alice, as_user, source):
    response = as_user(alice.user).post(EVIDENCE, {"source_type": source, "title": "Fake"}, format="json")
    assert response.status_code == 400


def test_request_verification_requires_tags_and_notifies_mentor(alice, taxonomy, faculty, as_user):
    client = as_user(alice.user)
    untagged = client.post(EVIDENCE, {"source_type": "project", "title": "X"}, format="json").json()
    assert client.post(f"{EVIDENCE}{untagged['id']}/request-verification/").status_code == 400

    tagged = client.post(
        EVIDENCE,
        {
            "source_type": "certification",
            "title": "AWS CCP",
            "tags": [{"skill_id": taxonomy("AWS").pk, "claimed_level": 1}],
        },
        format="json",
    ).json()
    response = client.post(f"{EVIDENCE}{tagged['id']}/request-verification/")
    assert response.status_code == 200
    assert response.json()["verification_status"] == "pending"
    assert faculty.notifications.filter(kind="verification_requested").exists()


def test_other_students_evidence_is_invisible(alice, make_student, taxonomy, as_user, give_evidence):
    bob = make_student(name="Bob")
    item = give_evidence(bob, SourceType.PROJECT, "Bob's project", [(taxonomy("Python"), Level.BEGINNER)])
    client = as_user(alice.user)
    assert client.get(f"{EVIDENCE}{item.pk}/").status_code == 404
    assert client.patch(f"{EVIDENCE}{item.pk}/", {"title": "hijack"}, format="json").status_code == 404
    assert client.delete(f"{EVIDENCE}{item.pk}/").status_code == 404
    assert client.get(EVIDENCE).json()["count"] == 0


def test_mentor_and_officer_can_read_but_not_edit(alice, faculty, officer, taxonomy, as_user, give_evidence):
    item = give_evidence(alice, SourceType.PROJECT, "P", [(taxonomy("Python"), Level.BEGINNER)])
    for user in (faculty, officer):
        client = as_user(user)
        assert client.get(f"{EVIDENCE}{item.pk}/").status_code == 200
        assert client.patch(f"{EVIDENCE}{item.pk}/", {"title": "x"}, format="json").status_code == 403


def test_unrelated_faculty_cannot_read(alice, make_user, taxonomy, as_user, give_evidence):
    from apps.accounts.roles import Role

    other = make_user(email="other-fac@example.test", roles=[Role.FACULTY])
    item = give_evidence(alice, SourceType.PROJECT, "P", [(taxonomy("Python"), Level.BEGINNER)])
    assert as_user(other).get(f"{EVIDENCE}{item.pk}/").status_code == 404


def test_verified_evidence_is_locked(alice, taxonomy, give_evidence):
    item = give_evidence(alice, SourceType.PROJECT, "P", [(taxonomy("Python"), Level.BEGINNER)], verified=True)
    with pytest.raises(EvidenceError):
        services.update_evidence(item, title="changed")
    with pytest.raises(EvidenceError):
        services.delete_evidence(item)


def test_editing_rejected_evidence_resets_to_self_reported(alice, taxonomy, give_evidence):
    item = give_evidence(alice, SourceType.PROJECT, "P", [(taxonomy("Python"), Level.BEGINNER)])
    services.set_status(item, VerificationStatus.REJECTED)
    services.update_evidence(item, title="Improved")
    item.refresh_from_db()
    assert item.verification_status == VerificationStatus.SELF_REPORTED


def test_tagging_rejects_duplicates_and_foreign_skills(alice, taxonomy):
    from apps.core.models import Institution
    from apps.taxonomy.services import create_skill

    python = taxonomy("Python")
    with pytest.raises(EvidenceError):
        services.submit_evidence(student=alice, source_type="project", title="X", tags=[(python, 1), (python, 2)])
    foreign = create_skill(institution=Institution.objects.create(name="O", code="o"), name="Rust")
    with pytest.raises(EvidenceError):
        services.submit_evidence(student=alice, source_type="project", title="X", tags=[(foreign, 1)])
    assert not EvidenceItem.objects.exists()
