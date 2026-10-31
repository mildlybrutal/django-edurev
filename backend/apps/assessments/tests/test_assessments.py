from datetime import date

import pytest

from apps.accounts.roles import Role
from apps.assessments.models import Rubric, RubricCriterion
from apps.assessments.services import percentage_to_level
from apps.evidence.models import EvidenceItem, VerificationStatus
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
ASSESSMENTS = "/api/v1/assessments/"


@pytest.fixture
def rubric(institution):
    r = Rubric.objects.create(institution=institution, name="Python practical", kind="technical")
    RubricCriterion.objects.create(rubric=r, name="Correctness", max_score=10, order=0)
    RubricCriterion.objects.create(rubric=r, name="Code quality", max_score=10, order=1)
    return r


def payload(student, rubric, skill, scores=(9, 8)):
    return {
        "student_id": student.pk,
        "rubric_id": rubric.pk,
        "title": "Python practical #1",
        "skill_id": skill.pk,
        "assessed_on": "2026-10-01",
        "scores": [{"criterion_id": c.pk, "score": s} for c, s in zip(rubric.criteria.all(), scores, strict=True)],
    }


@pytest.mark.parametrize(
    "pct,level", [(95, Level.EXPERT), (75, Level.ADVANCED), (50, Level.INTERMEDIATE), (10, Level.BEGINNER)]
)
def test_percentage_to_level(pct, level):
    assert percentage_to_level(pct) == level


def test_mentor_records_rubric_assessment_as_verified_evidence(make_student, faculty, rubric, taxonomy, as_user):
    alice = make_student()
    response = as_user(faculty).post(ASSESSMENTS, payload(alice, rubric, taxonomy("Python")), format="json")
    assert response.status_code == 201, response.content
    assert response.json()["percentage"] == "85.00"
    item = EvidenceItem.objects.get(student=alice)
    assert item.verification_status == VerificationStatus.VERIFIED
    assert item.skill_tags.get().claimed_level == Level.ADVANCED


def test_score_above_criterion_maximum_rejected(make_student, faculty, rubric, taxonomy, as_user):
    response = as_user(faculty).post(
        ASSESSMENTS, payload(make_student(), rubric, taxonomy("Python"), (11, 8)), format="json"
    )
    assert response.status_code == 400


def test_every_criterion_must_be_scored(make_student, faculty, rubric, taxonomy, as_user):
    data = payload(make_student(), rubric, taxonomy("Python"))
    data["scores"] = data["scores"][:1]
    assert as_user(faculty).post(ASSESSMENTS, data, format="json").status_code == 400


def test_non_mentor_faculty_and_students_cannot_assess(make_student, make_user, rubric, taxonomy, as_user):
    alice = make_student()
    stranger = make_user(email="f9@example.test", roles=[Role.FACULTY])
    # The student is outside the stranger's scope, so it is not even revealed to exist.
    assert (
        as_user(stranger).post(ASSESSMENTS, payload(alice, rubric, taxonomy("Python")), format="json").status_code
        == 404
    )
    assert (
        as_user(alice.user).post(ASSESSMENTS, payload(alice, rubric, taxonomy("Python")), format="json").status_code
        == 403
    )


def test_mock_interview_feeds_communication_and_skills(make_student, officer, taxonomy, as_user):
    alice = make_student()
    response = as_user(officer).post(
        f"{ASSESSMENTS}mock-interviews/",
        {
            "student_id": alice.pk,
            "conducted_on": "2026-10-02",
            "role_focus": "Backend Engineer",
            "technical_score": 70,
            "communication_score": 80,
            "problem_solving_score": 65,
            "feedback": "Clear explanations.",
            "skill_ratings": [{"skill_id": taxonomy("Django").pk, "level": 2}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert as_user(alice.user).get(f"{ASSESSMENTS}mock-interviews/").json()["count"] == 1


def test_history_is_visible_to_student_only_for_self(make_student, faculty, rubric, taxonomy, as_user):
    alice, bob = make_student(), make_student()
    as_user(faculty).post(ASSESSMENTS, payload(alice, rubric, taxonomy("Python")), format="json")
    assert as_user(alice.user).get(ASSESSMENTS).json()["count"] == 1
    assert as_user(bob.user).get(ASSESSMENTS).json()["count"] == 0
    assert date.fromisoformat(as_user(alice.user).get(ASSESSMENTS).json()["results"][0]["assessed_on"])
