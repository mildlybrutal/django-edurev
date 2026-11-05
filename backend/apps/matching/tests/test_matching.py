import pytest

from apps.drives.models import EligibilityResult, RuleType
from apps.evidence.models import SourceType
from apps.matching import services
from apps.matching.models import GapAnalysis, GapKind, MatchResult
from apps.readiness.models import ReadinessSnapshot
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
INT, BEG, ADV = Level.INTERMEDIATE, Level.BEGINNER, Level.ADVANCED


def breakdown(drive, student):
    services.match_student(drive, student)
    return {r["skill"]: r for r in MatchResult.objects.get(drive=drive, student=student).breakdown}


def test_exact_match(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), INT)], verified=True)
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)])
    row = breakdown(drive, s)["Django"]
    assert (row["match"], row["credit"]) == ("exact", 1.0)
    assert float(MatchResult.objects.get(drive=drive, student=s).compatibility) == 100.0


def test_synonym_match(make_student, make_drive, taxonomy, give_evidence):
    """Evidence tagged via the synonym 'Postgres' satisfies a 'PostgreSQL' requirement."""
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "DB", [(taxonomy("Postgres"), INT)], verified=True)
    drive = make_drive(requirements=[(taxonomy("PostgreSQL"), INT, 1, False)])
    assert breakdown(drive, s)["PostgreSQL"]["credit"] == 1.0


def test_taxonomy_expanded_match(make_student, make_drive, taxonomy, give_evidence):
    """React satisfies a requirement for 'Frontend Framework' (P06 §8)."""
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "UI", [(taxonomy("React"), INT)], verified=True)
    drive = make_drive(requirements=[(taxonomy("Frontend Framework"), INT, 1, False)])
    row = breakdown(drive, s)["Frontend Framework"]
    assert (row["match"], row["matched_skill"], row["credit"]) == ("taxonomy", "React", 1.0)


def test_expansion_does_not_go_upwards(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "UI", [(taxonomy("Frontend Framework"), INT)], verified=True)
    drive = make_drive(requirements=[(taxonomy("React"), INT, 1, False)])
    assert breakdown(drive, s)["React"]["match"] == "none"


def test_missing_skill(make_student, make_drive, taxonomy):
    s = make_student()
    drive = make_drive(requirements=[(taxonomy("Docker"), INT, 1, True)])
    row = breakdown(drive, s)["Docker"]
    assert (row["match"], row["credit"], row["level"]) == ("none", 0.0, 0)


def test_partial_match_and_weighting(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), BEG)], verified=True)
    drive = make_drive(requirements=[(taxonomy("Django"), ADV, 3, True), (taxonomy("Docker"), BEG, 1, False)])
    rows = breakdown(drive, s)
    assert rows["Django"]["credit"] == pytest.approx(1 / 3, abs=1e-4)
    # (1/3 × 3 + 0 × 1) / 4 = 25%
    assert float(MatchResult.objects.get(drive=drive, student=s).compatibility) == pytest.approx(25.0, abs=0.01)


def test_unverified_evidence_counts_at_the_configured_multiplier(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), INT)])  # unverified, capped at Intermediate
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)])
    assert breakdown(drive, s)["Django"]["credit"] == pytest.approx(0.5)


def test_gaps_are_ranked_specific_and_actionable(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), BEG)], verified=True)
    give_evidence(s, SourceType.PROJECT, "Ops", [(taxonomy("Docker"), INT)])
    drive = make_drive(
        requirements=[
            (taxonomy("Django"), ADV, 3, True),
            (taxonomy("Docker"), INT, 2, False),
            (taxonomy("Frontend Framework"), INT, 1, False),
            (taxonomy("Python"), BEG, 1, False),
        ]
    )
    services.match_student(drive, s)
    items = list(GapAnalysis.objects.get(drive=drive, student=s).items.select_related("skill"))
    assert [g.rank for g in items] == list(range(1, len(items) + 1))
    assert [float(g.impact_score) for g in items] == sorted((float(g.impact_score) for g in items), reverse=True)
    by_skill = {g.skill.name: g for g in items}
    assert by_skill["Django"].kind == GapKind.BELOW_LEVEL and by_skill["Django"].impact == "high"
    assert by_skill["Docker"].kind == GapKind.UNVERIFIED
    assert by_skill["Frontend Framework"].kind == GapKind.MISSING
    assert "React" in by_skill["Frontend Framework"].suggested_action  # concrete example from the taxonomy
    assert "Beginner to Advanced" in by_skill["Django"].suggested_action
    assert "verify" in by_skill["Docker"].suggested_action.lower()


def test_eligibility_and_readiness_are_independent(make_student, make_drive, taxonomy, give_evidence):
    """All four combinations must be representable (AGENTS.md §8)."""
    django = taxonomy("Django")
    drive = make_drive(requirements=[(django, INT, 1, True)], rules=[(RuleType.MIN_CGPA, 7.0)])
    eligible_strong = make_student(cgpa="8.0")
    eligible_weak = make_student(cgpa="8.0")
    ineligible_strong = make_student(cgpa="6.0")
    ineligible_weak = make_student(cgpa="6.0")
    for s in (eligible_strong, ineligible_strong):
        give_evidence(s, SourceType.PROJECT, "API", [(django, INT)], verified=True)

    services.run_drive_matching(drive)
    state = {
        s.pk: (
            EligibilityResult.objects.get(drive=drive, student=s).is_eligible,
            float(MatchResult.objects.get(drive=drive, student=s).compatibility),
        )
        for s in (eligible_strong, eligible_weak, ineligible_strong, ineligible_weak)
    }
    assert state[eligible_strong.pk] == (True, 100.0)
    assert state[eligible_weak.pk] == (True, 0.0)
    assert state[ineligible_strong.pk] == (False, 100.0)  # not eligible, yet a strong skill match
    assert state[ineligible_weak.pk] == (False, 0.0)


def test_drive_matching_job_records_drive_readiness(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), INT)], verified=True)
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)])
    summary = services.run_drive_matching(drive)
    assert summary == {"students": 1, "eligible": 1, "average_compatibility": 100.0}
    snap = ReadinessSnapshot.objects.get(student=s, drive=drive)
    assert float(snap.technical) == 100.0  # technical mastery is drive-specific
    assert snap.explanation["dimensions"]["technical"]["inputs"][0]["skill"] == "Django"


def test_student_evaluation_api_keeps_blocks_separate(make_student, make_drive, taxonomy, as_user):
    s = make_student(cgpa="6.0")
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)], rules=[(RuleType.MIN_CGPA, 7.0)])
    body = as_user(s.user).get(f"/api/v1/drives/{drive.pk}/my-evaluation/").json()
    assert set(body) >= {"eligibility", "compatibility", "readiness", "gaps"}
    assert body["eligibility"]["is_eligible"] is False
    assert "score" not in body["eligibility"]
    assert body["compatibility"]["score"] == 0.0
    assert body["gaps"][0]["skill"] == "Django"


def test_officer_match_list_shows_eligibility_and_compatibility(
    make_student, make_drive, taxonomy, officer, as_user, django_capture_on_commit_callbacks
):
    make_student(cgpa="8.0")
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)], rules=[(RuleType.MIN_CGPA, 7.0)])
    client = as_user(officer)
    with django_capture_on_commit_callbacks(execute=True):
        job = client.post(f"/api/v1/drives/{drive.pk}/match/").json()
    assert job["kind"] == "drive_matching"
    body = client.get(f"/api/v1/drives/{drive.pk}/match/").json()
    assert body["summary"]["evaluated"] == 1 and body["summary"]["eligible"] == 1
    row = body["results"][0]
    assert {"eligible", "compatibility", "readiness"} <= set(row)


def test_profile_recompute_refreshes_stored_drive_results(make_student, make_drive, taxonomy, give_evidence):
    """Officers and recruiters read stored results; they must follow profile changes."""
    from apps.profiles.tasks import recompute_student

    s = make_student()
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)])
    services.match_student(drive, s)
    assert float(MatchResult.objects.get(drive=drive, student=s).compatibility) == 0.0
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), INT)], verified=True)
    recompute_student(s.pk)
    assert float(MatchResult.objects.get(drive=drive, student=s).compatibility) == 100.0


def test_batch_readiness_rematches_active_drives(make_student, make_drive, taxonomy, give_evidence):
    from apps.reporting.services import run_batch_readiness

    s = make_student()
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)])
    services.match_student(drive, s)
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), INT)], verified=True)
    result = run_batch_readiness(s.institution_id, nudge_below=None)
    assert result["drives_rematched"] == 1
    assert float(MatchResult.objects.get(drive=drive, student=s).compatibility) == 100.0


def test_publishing_notifies_students_of_a_match_or_the_missed_criteria(
    make_student, make_drive, taxonomy, give_evidence
):
    """P06 notifications: 'new drive matching profile' and 'eligibility met/missed with reason'."""
    from apps.notifications.models import Notification

    eligible = make_student(cgpa="8.50")
    give_evidence(eligible, SourceType.PROJECT, "API", [(taxonomy("Django"), INT)], verified=True)
    ineligible = make_student(cgpa="6.20")
    drive = make_drive(requirements=[(taxonomy("Django"), INT, 1, True)], rules=[(RuleType.MIN_CGPA, 7.0)])

    services.run_drive_matching(drive, notify_students=True)

    match = Notification.objects.get(recipient=eligible.user)
    assert match.kind == "new_drive_match"
    assert "100% skill match" in match.title and match.link == f"/student/drives/{drive.pk}"
    missed = Notification.objects.get(recipient=ineligible.user)
    assert missed.kind == "eligibility_missed"
    assert "CGPA" in missed.body  # the failed criterion is named, not just "not eligible"


def test_rematching_without_the_flag_sends_nothing(make_student, make_drive, taxonomy):
    from apps.notifications.models import Notification

    make_student()
    services.run_drive_matching(make_drive(requirements=[(taxonomy("Django"), INT, 1, True)]))
    assert not Notification.objects.exists()
