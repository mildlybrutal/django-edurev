from datetime import timedelta

import pytest
from django.utils import timezone

from apps.drives import services
from apps.drives.eligibility import evaluate
from apps.drives.jd import process_jd
from apps.drives.models import DriveStatus, JDStatus, RuleType
from apps.drives.services import DriveError
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
DRIVES = "/api/v1/drives/"

RULES = [
    (RuleType.MIN_CGPA, 7.0),
    (RuleType.MAX_ACTIVE_BACKLOGS, 0),
    (RuleType.DEPARTMENT_IN, ["CSE", "IT"]),
    (RuleType.GRADUATION_YEAR_IN, [2027]),
]


def test_eligible_student_passes_every_rule(make_student, make_drive):
    drive = make_drive(rules=RULES)
    ok, reasons = evaluate(make_student(cgpa="8.10"), drive.eligibility_rules.all())
    assert ok and len(reasons) == 4 and all(r["passed"] for r in reasons)


def test_ineligible_student_gets_each_failed_reason(make_student, make_drive):
    drive = make_drive(rules=RULES)
    student = make_student(cgpa="6.50", backlogs=2, dept="ECE", year=2026)
    ok, reasons = evaluate(student, drive.eligibility_rules.all())
    assert not ok
    failed = {r["rule"]: r["message"] for r in reasons if not r["passed"]}
    assert set(failed) == {"min_cgpa", "max_active_backlogs", "department_in", "graduation_year_in"}
    assert failed["min_cgpa"] == "CGPA 6.50 is below 7.0"


def test_one_failed_rule_makes_student_ineligible(make_student, make_drive):
    drive = make_drive(rules=RULES)
    ok, reasons = evaluate(make_student(backlogs=1), drive.eligibility_rules.all())
    assert not ok
    assert [r["rule"] for r in reasons if not r["passed"]] == ["max_active_backlogs"]


@pytest.mark.parametrize(
    "rule,value",
    [
        (RuleType.MIN_CGPA, 11),
        (RuleType.MAX_ACTIVE_BACKLOGS, -1),
        (RuleType.DEPARTMENT_IN, []),
        (RuleType.GRADUATION_YEAR_IN, ["x"]),
    ],
)
def test_invalid_rule_values_rejected(make_drive, rule, value):
    with pytest.raises(DriveError):
        services.set_eligibility_rule(make_drive(), rule, value)


def test_register_blocked_when_ineligible_and_allowed_when_eligible(make_student, make_drive, as_user):
    drive = make_drive(rules=[(RuleType.MIN_CGPA, 7.5)])
    weak, strong = make_student(cgpa="7.00"), make_student(cgpa="8.00")
    response = as_user(weak.user).post(f"{DRIVES}{drive.pk}/register/")
    assert response.status_code == 400
    assert "below 7.5" in str(response.json())
    assert as_user(strong.user).post(f"{DRIVES}{drive.pk}/register/").status_code == 201
    assert as_user(strong.user).post(f"{DRIVES}{drive.pk}/register/").status_code == 400  # duplicate


def test_registration_window_enforced(make_student, make_drive):
    drive = make_drive()
    drive.registration_closes_at = timezone.now() - timedelta(minutes=1)
    drive.save()
    with pytest.raises(DriveError):
        services.register(drive, make_student())


def test_students_never_see_draft_drives(make_student, make_drive, as_user):
    draft = make_drive(publish=False)
    published = make_drive(role="Data Analyst")
    client = as_user(make_student().user)
    ids = [d["id"] for d in client.get(DRIVES).json()["results"]]
    assert ids == [published.pk]
    assert client.get(f"{DRIVES}{draft.pk}/").status_code == 404


def test_students_and_faculty_cannot_manage_drives(make_student, faculty, as_user, make_drive):
    drive = make_drive()
    for user in (make_student().user, faculty):
        client = as_user(user)
        assert client.post(DRIVES, {"role_title": "x", "company_id": 1}, format="json").status_code == 403
        assert client.patch(f"{DRIVES}{drive.pk}/", {"role_title": "x"}, format="json").status_code == 403
        assert client.post(f"{DRIVES}{drive.pk}/match/").status_code == 403


def test_lifecycle_transitions(make_drive, officer, taxonomy):
    drive = make_drive(publish=False)
    with pytest.raises(DriveError):
        services.transition(drive, DriveStatus.PUBLISHED, actor=officer)  # no requirements yet
    services.set_requirement(drive, skill=taxonomy("Django"), required_level=2, weight=3, is_mandatory=True)
    services.transition(drive, DriveStatus.PUBLISHED, actor=officer)
    with pytest.raises(DriveError):
        services.transition(drive, DriveStatus.COMPLETED, actor=officer)  # must close registration first
    services.transition(drive, DriveStatus.REGISTRATION_CLOSED, actor=officer)
    with pytest.raises(DriveError):
        services.set_requirement(drive, skill=taxonomy("Docker"), required_level=1, weight=1, is_mandatory=False)


def test_shortlisting_notifies_student(make_student, make_drive, officer, as_user):
    drive = make_drive()
    student = make_student()
    registration = services.register(drive, student)
    drive.status = DriveStatus.REGISTRATION_CLOSED
    drive.save()
    response = as_user(officer).post(
        f"{DRIVES}{drive.pk}/registrations/{registration.pk}/decide/", {"status": "shortlisted"}, format="json"
    )
    assert response.status_code == 200
    assert student.user.notifications.filter(kind="shortlist_result").exists()


SAMPLE_JD = """
Backend Engineer — Synthetic Corp (2027 batch)
We are looking for engineers with strong Python and Django skills. Must have experience building REST APIs
and working with PostgreSQL. Familiarity with Docker is required. Good to have: exposure to Redis and React.
Solid understanding of DSA is essential.
Eligibility: B.Tech CSE / IT, minimum 7.5 CGPA, no active backlogs.
"""


def test_jd_extraction_maps_skills_levels_and_eligibility(institution, taxonomy, departments):
    result = process_jd(SAMPLE_JD, institution.id)
    skills = {s["skill"]: s for s in result["skills"]}
    assert {
        "Python",
        "Django",
        "REST APIs",
        "PostgreSQL",
        "Docker",
        "Redis",
        "React",
        "Data Structures & Algorithms",
    } <= set(skills)
    assert skills["Django"]["required_level"] == Level.ADVANCED
    assert skills["Docker"]["required_level"] == Level.BEGINNER and skills["Docker"]["is_mandatory"]
    assert not skills["React"]["is_mandatory"]
    assert skills["PostgreSQL"]["is_mandatory"]
    rules = {r["rule_type"]: r["value"] for r in result["eligibility"]}
    assert rules == {
        "min_cgpa": 7.5,
        "max_active_backlogs": 0,
        "department_in": ["CSE", "IT"],
        "graduation_year_in": [2027],
    }


def test_jd_workflow_via_api(make_drive, taxonomy, departments, officer, as_user, django_capture_on_commit_callbacks):
    drive = make_drive(publish=False)
    client = as_user(officer)
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(f"{DRIVES}{drive.pk}/jd/", {"text": SAMPLE_JD}, format="json").status_code == 202
    body = client.get(f"{DRIVES}{drive.pk}/jd/").json()
    assert body["status"] == JDStatus.READY
    chosen = [s for s in body["extraction"]["skills"] if s["is_mandatory"]]
    response = client.post(
        f"{DRIVES}{drive.pk}/jd/apply/",
        {
            "skills": [{k: s[k] for k in ("skill_id", "required_level", "weight", "is_mandatory")} for s in chosen],
            "rules": [{"rule_type": r["rule_type"], "value": r["value"]} for r in body["extraction"]["eligibility"]],
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    applied = response.json()
    assert {r["skill"] for r in applied["requirements"]} == {s["skill"] for s in chosen}
    assert {r["source"] for r in applied["requirements"]} == {"jd"}
    assert len(applied["eligibility_rules"]) == 4
    drive.refresh_from_db()
    assert drive.jd_status == JDStatus.APPLIED


def test_role_template_seeds_requirements(make_drive, taxonomy, institution):
    from apps.taxonomy.models import TargetRole

    drive = make_drive(publish=False)
    services.apply_role_template(drive, TargetRole.objects.get(institution=institution, slug="data-analyst"))
    assert drive.requirements.count() >= 8


def test_jd_sentence_splitting_keeps_wrapped_lines_together(institution, taxonomy):
    text = "Must have experience with REST APIs\nand PostgreSQL.\n\n- Nice to have: React"
    skills = {s["skill"]: s for s in process_jd(text, institution.id)["skills"]}
    assert skills["PostgreSQL"]["is_mandatory"]
    assert not skills["React"]["is_mandatory"]
