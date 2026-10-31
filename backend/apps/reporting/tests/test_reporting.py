import pytest

from apps.core.models import BackgroundJob, JobStatus
from apps.drives import services as drive_services
from apps.drives.models import DriveStatus, RuleType
from apps.evidence.models import SourceType
from apps.matching.services import run_drive_matching
from apps.reporting import services
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
INT = Level.INTERMEDIATE


def test_distribution_bands():
    rows = {r["band"]: r["count"] for r in services.distribution([95, 80, 79.9, 60, 45, 10, 0])}
    assert rows == {"80–100%": 2, "60–80%": 2, "40–60%": 1, "<40%": 2}


def test_supply_demand_for_drive(make_student, make_drive, taxonomy, give_evidence):
    a, b, c, _ = make_student(), make_student(), make_student(), make_student()
    give_evidence(a, SourceType.PROJECT, "x", [(taxonomy("Django"), INT)], verified=True)
    give_evidence(b, SourceType.PROJECT, "x", [(taxonomy("Django"), INT), (taxonomy("React"), INT)], verified=True)
    give_evidence(c, SourceType.PROJECT, "x", [(taxonomy("Django"), Level.BEGINNER)])
    drive = make_drive(
        requirements=[(taxonomy("Django"), INT, 3, True), (taxonomy("Frontend Framework"), INT, 1, False)]
    )
    report = services.supply_demand_for_drive(drive)
    rows = {r["skill"]: r for r in report["requirements"]}
    assert report["students"] == 4
    assert rows["Django"]["supply_percent"] == 50.0  # a and b meet Intermediate
    assert rows["Django"]["any_evidence_percent"] == 75.0
    assert rows["Frontend Framework"]["supply_percent"] == 25.0  # b via React
    assert rows["Django"]["demand_share"] == 75.0


def test_overview_and_funnel(make_student, make_drive, taxonomy, give_evidence, officer):
    s1 = make_student(cgpa="8.0")
    make_student(cgpa="6.0")
    give_evidence(s1, SourceType.PROJECT, "x", [(taxonomy("Django"), INT)], verified=True)
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)], rules=[(RuleType.MIN_CGPA, 7.0)])
    run_drive_matching(drive)
    services.run_batch_readiness(drive.institution_id)
    registration = drive_services.register(drive, s1)
    drive.status = DriveStatus.REGISTRATION_CLOSED
    drive.save()
    drive_services.decide_registration(registration, "shortlisted", actor=officer)

    overview = services.overview(drive.institution_id)
    assert overview["total_students"] == 2
    assert overview["active_drives"] == 1
    assert overview["eligible_students"] == 1
    assert overview["students_with_readiness"] == 2
    assert sum(b["count"] for b in overview["readiness_distribution"]) == 2
    assert overview["recent_drives"][0]["eligible"] == 1
    funnel = {x["stage"]: x["count"] for x in services.drive_funnel(drive)["stages"]}
    assert funnel == {"Evaluated": 2, "Eligible": 1, "Registered": 1, "Shortlisted": 1, "Selected": 0}


def test_gap_frequency_and_verification_coverage(make_student, make_drive, taxonomy, give_evidence):
    a, b = make_student(), make_student()
    give_evidence(a, SourceType.PROJECT, "x", [(taxonomy("Django"), INT)], verified=True)
    give_evidence(b, SourceType.CERTIFICATION, "y", [(taxonomy("AWS"), Level.BEGINNER)])
    drive = make_drive(requirements=[(taxonomy("Docker"), INT, 1, True)])
    run_drive_matching(drive)
    gaps = services.gap_frequency(drive.institution_id, drive=drive)
    assert gaps[0]["skill"] == "Docker" and gaps[0]["students"] == 2
    coverage = services.verification_coverage(drive.institution_id)
    assert coverage["total_evidence"] == 2
    assert coverage["by_status"]["verified"] == 1
    assert coverage["student_coverage_percent"] == 50.0


def test_batch_readiness_job_and_low_readiness_nudge(
    make_student, faculty, institution, django_capture_on_commit_callbacks
):
    make_student()
    with django_capture_on_commit_callbacks(execute=True):
        job = services.start_batch_readiness_job(institution.id)
    job.refresh_from_db()
    assert job.status == JobStatus.SUCCEEDED
    assert job.result["students"] == 1 and job.processed == 1
    assert faculty.notifications.filter(kind="low_readiness_mentee").exists()
    assert BackgroundJob.objects.filter(kind="batch_readiness").count() == 1


def test_reports_require_placement_roles(make_student, faculty, officer, head, as_user):
    for user in (make_student().user, faculty):
        assert as_user(user).get("/api/v1/reports/overview/").status_code == 403
    assert as_user(officer).get("/api/v1/reports/overview/").status_code == 200
    # Institutional analytics are for the placement head (P06 §6).
    assert as_user(officer).get("/api/v1/reports/departments/").status_code == 403
    assert as_user(head).get("/api/v1/reports/departments/").status_code == 200
    assert as_user(head).get("/api/v1/reports/training-effectiveness/").status_code == 200


def test_student_dashboard(make_student, make_drive, taxonomy, give_evidence, as_user):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "x", [(taxonomy("Django"), INT)], verified=True)
    make_drive(requirements=[(taxonomy("Django"), INT, 1, True)])
    body = as_user(s.user).get("/api/v1/dashboard/student/").json()
    assert body["cards"]["verified_evidence"] == 1
    assert body["drives"][0]["compatibility"] == 100.0
    assert body["drives"][0]["is_eligible"] is True
    assert body["skills"][0]["skill"] == "Django"


def test_student_dashboard_plan_budget_and_module_clusters(make_student, make_drive, taxonomy, give_evidence, as_user):
    from datetime import timedelta

    from django.utils import timezone

    from apps.evidence.models import SourceType
    from apps.matching.services import match_student
    from apps.planning.services import generate_plan
    from apps.taxonomy.models import Level

    student = make_student()
    give_evidence(student, SourceType.PROJECT, "API", [(taxonomy("Django"), Level.BEGINNER)])
    today = timezone.localdate()
    drive = make_drive(
        requirements=[(taxonomy("Django"), Level.ADVANCED, 1, True)], drive_date=today + timedelta(days=20)
    )
    match_student(drive, student)
    generate_plan(student, drive, today=today)
    body = as_user(student.user).get("/api/v1/dashboard/student/").json()
    plan = body["plan"]
    assert plan["drive_date"] == str(drive.drive_date)
    assert plan["days_left"] == 20 and plan["done"] == 0 and plan["total"] >= 1
    assert body["tasks"][0]["cluster"] == taxonomy("Django").cluster.slug
    assert {s["skill"]: s["cluster"] for s in body["skills"]}["Django"] == taxonomy("Django").cluster.slug


def test_gap_frequency_counts_students_not_gap_rows(make_student, make_drive, taxonomy):
    """Regression: a student with the same gap on two drives was counted twice in high/missing."""
    from apps.matching.services import match_student
    from apps.reporting import services as reporting
    from apps.taxonomy.models import Level

    student = make_student()
    for company in ("Acme", "Globex"):
        drive = make_drive(company=company, requirements=[(taxonomy("Docker"), Level.INTERMEDIATE, 1, True)])
        match_student(drive, student)
    row = next(r for r in reporting.gap_frequency(student.institution_id) if r["skill"] == "Docker")
    assert row["students"] == 1
    assert row["missing"] == 1 and row["high_impact"] <= 1
    assert row["cluster"] == taxonomy("Docker").cluster.slug
