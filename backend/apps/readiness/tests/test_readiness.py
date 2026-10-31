from datetime import date

import pytest

from apps.assessments.models import Assessment, MockInterview, Rubric
from apps.core.models import ImmutableRecordError
from apps.evidence.models import SourceType
from apps.readiness import services
from apps.readiness.models import ReadinessSnapshot
from apps.readiness.policy import credited_level, weighted_overall
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db


def test_credited_level_discounts_only_the_unverified_part():
    assert credited_level(3, 3, 0.5) == 3
    assert credited_level(3, 1, 0.5) == 2.0
    assert credited_level(2, 0, 0.5) == 1.0


def test_weighted_overall():
    scores = {"technical": 80, "aptitude": 60, "communication": 50, "project_depth": 100}
    assert weighted_overall(scores, {"technical": 40, "aptitude": 20, "communication": 20, "project_depth": 20}) == 74


def _assess(student, kind, pct, by):
    rubric = Rubric.objects.get_or_create(institution_id=student.institution_id, name=kind, kind=kind)[0]
    Assessment.objects.create(
        institution_id=student.institution_id,
        student=student,
        rubric=rubric,
        kind=kind,
        title=kind,
        assessed_by=by,
        assessed_on=date(2026, 10, 1),
        total_score=pct,
        max_score=100,
        percentage=pct,
    )


def test_dimension_level_calculation(make_student, taxonomy, give_evidence, faculty):
    alice = make_student()
    give_evidence(
        alice,
        SourceType.PROJECT,
        "API",
        [
            (taxonomy("Django"), Level.EXPERT),
            (taxonomy("PostgreSQL"), Level.ADVANCED),
            (taxonomy("Docker"), Level.INTERMEDIATE),
        ],
        verified=True,
    )
    _assess(alice, "aptitude", 70, faculty)
    _assess(alice, "communication", 60, faculty)
    MockInterview.objects.create(
        institution_id=alice.institution_id,
        student=alice,
        interviewer=faculty,
        conducted_on=date(2026, 10, 2),
        technical_score=50,
        communication_score=80,
        problem_solving_score=50,
    )
    snap = services.compute_general_snapshot(alice)
    # technical: credited levels 4,3,2 of 4 -> 75%; project: 1 verified project with 3 skills / target 3 -> 33.33
    assert float(snap.technical) == 75.0
    assert float(snap.aptitude) == 70.0
    assert float(snap.communication) == 70.0
    assert float(snap.project_depth) == pytest.approx(33.33, abs=0.01)
    assert float(snap.coding_activity) == 0  # no coding profiles linked
    # weights 40/20/20/20/10 (coding activity included even when it scores 0)
    assert float(snap.overall) == pytest.approx((40 * 75 + 20 * 70 + 20 * 70 + 20 * 33.33) / 110, abs=0.01)
    dims = snap.explanation["dimensions"]
    assert dims["technical"]["inputs"][0]["skill"] == "Django"
    assert snap.explanation["config_version"] == 1


def test_missing_dimensions_score_zero_with_explanation(make_student):
    snap = services.compute_general_snapshot(make_student())
    assert float(snap.overall) == 0
    assert snap.explanation["dimensions"]["aptitude"]["missing"]


def test_readiness_increases_after_new_evidence(make_student, taxonomy, give_evidence):
    alice = make_student()
    before = services.compute_general_snapshot(alice)
    give_evidence(alice, SourceType.PROJECT, "API", [(taxonomy("Django"), Level.INTERMEDIATE)])
    after = services.compute_general_snapshot(alice)
    assert after.overall > before.overall
    assert ReadinessSnapshot.objects.filter(student=alice).count() == 2


def test_snapshots_are_immutable(make_student):
    snap = services.compute_general_snapshot(make_student())
    snap.overall = 99
    with pytest.raises(ImmutableRecordError):
        snap.save()


def test_new_config_version_changes_results_and_keeps_history(make_student, taxonomy, give_evidence, admin_user):
    alice = make_student()
    give_evidence(alice, SourceType.PROJECT, "API", [(taxonomy("Django"), Level.INTERMEDIATE)])
    first = services.compute_general_snapshot(alice)
    services.publish_config(
        institution=alice.institution,
        created_by=admin_user,
        weight_technical=100,
        weight_aptitude=0,
        weight_communication=0,
        weight_project_depth=0,
        weight_coding=0,
    )
    second = services.compute_general_snapshot(alice)
    assert second.config.version == 2 and first.config.version == 1
    assert float(second.overall) == float(second.technical)
    first.refresh_from_db()
    assert first.config.version == 1  # old snapshot still explains itself


def test_readiness_endpoint_explains_result(make_student, taxonomy, give_evidence, as_user):
    alice = make_student()
    give_evidence(alice, SourceType.PROJECT, "API", [(taxonomy("Django"), Level.INTERMEDIATE)])
    services.compute_general_snapshot(alice)
    body = as_user(alice.user).get("/api/v1/students/me/readiness/").json()
    assert set(body["latest"]["explanation"]["dimensions"]) == {
        "technical",
        "aptitude",
        "communication",
        "project_depth",
        "coding_activity",
    }
    assert len(body["history"]) == 1


def test_only_admin_publishes_config(officer, admin_user, as_user):
    assert (
        as_user(officer).post("/api/v1/readiness/config/", {"weight_technical": 50}, format="json").status_code == 403
    )
    response = as_user(admin_user).post("/api/v1/readiness/config/", {"weight_technical": 50}, format="json")
    assert response.status_code == 201
    assert response.json()["version"] == 2
