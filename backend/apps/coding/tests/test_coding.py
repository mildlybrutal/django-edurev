from unittest import mock

import pytest

from apps.coding import clients, rating, services
from apps.coding.models import CodingProfile, SyncStatus
from apps.evidence.models import SourceType, VerificationStatus
from apps.profiles.models import SkillClaim
from apps.profiles.services import recompute_profile
from apps.readiness.services import compute_general_snapshot
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db

GITHUB_STATS = {
    "username": "sana-dev",
    "profile_url": "https://github.com/sana-dev",
    "public_repos": 12,
    "original_repos": 9,
    "stars": 40,
    "followers": 5,
    "languages": {"Python": 5, "TypeScript": 3, "Go": 1},
    "recent_push_events": 24,
    "repos_pushed_90d": 4,
    "top_repos": [],
}
LEETCODE_STATS = {
    "username": "sana",
    "profile_url": "https://leetcode.com/u/sana/",
    "solved_easy": 120,
    "solved_medium": 150,
    "solved_hard": 30,
    "solved_total": 300,
    "contest_rating": 1650,
    "contests_attended": 8,
}


def test_github_rating_is_explainable_and_saturating():
    score, exp = rating.github_rating(GITHUB_STATS)
    parts = {c["key"]: c for c in exp["components"]}
    assert 0 < score <= 100
    assert parts["activity"]["points"] == pytest.approx(100 * 0.35 * 24 / 30, abs=0.1)
    assert parts["breadth"]["points"] == pytest.approx(100 * 0.20 * 3 / 5, abs=0.1)
    huge, _ = rating.github_rating({**GITHUB_STATS, "stars": 10**9, "recent_push_events": 10**6})
    assert huge <= 100


def test_leetcode_rating_weights_difficulty_and_contest():
    score, exp = rating.leetcode_rating(LEETCODE_STATS)
    parts = {c["key"]: c for c in exp["components"]}
    weighted = 120 + 2 * 150 + 3 * 30  # 510
    assert parts["solved"]["points"] == pytest.approx(70 * weighted / 600, abs=0.1)
    assert parts["contest"]["points"] == pytest.approx(30 * 450 / 1000, abs=0.1)
    no_contest, exp2 = rating.leetcode_rating({**LEETCODE_STATS, "contest_rating": None})
    assert [c["key"] for c in exp2["components"]] == ["solved"]
    assert no_contest == pytest.approx(100 * min(1, weighted / 600), abs=0.1)


@pytest.mark.parametrize(
    "solved,level", [(10, Level.BEGINNER), (60, Level.INTERMEDIATE), (250, Level.ADVANCED), (900, Level.EXPERT)]
)
def test_leetcode_claimed_dsa_level(solved, level):
    assert rating.leetcode_dsa_level({"solved_total": solved}) == level


def test_usernames_are_validated_before_any_request():
    with pytest.raises(clients.ProfileNotFound):
        clients.fetch_github("../../evil")
    with pytest.raises(clients.ProfileNotFound):
        clients.fetch_leetcode("a b")
    with pytest.raises(services.CodingError):
        services.validate_username("github", "-bad-")


def test_github_client_reduces_api_payload():
    responses = [
        {"login": "sana-dev", "html_url": "https://github.com/sana-dev", "public_repos": 3, "followers": 1},
        [
            {
                "name": "api",
                "fork": False,
                "language": "Python",
                "stargazers_count": 3,
                "pushed_at": "2026-10-01T00:00:00Z",
                "html_url": "x",
            },
            {
                "name": "fork",
                "fork": True,
                "language": "C",
                "stargazers_count": 100,
                "pushed_at": "2026-10-01T00:00:00Z",
            },
        ],
        [
            {"type": "PushEvent", "created_at": "2026-10-10T00:00:00Z"},
            {"type": "WatchEvent", "created_at": "2026-10-10T00:00:00Z"},
        ],
    ]
    from datetime import UTC, datetime

    with mock.patch.object(clients, "_request", side_effect=responses):
        stats = clients.fetch_github("sana-dev", now=datetime(2026, 10, 21, tzinfo=UTC))
    assert stats["original_repos"] == 1 and stats["stars"] == 3  # forks excluded
    assert stats["languages"] == {"Python": 1}
    assert stats["recent_push_events"] == 1 and stats["repos_pushed_90d"] == 1


def test_leetcode_client_parses_graphql():
    payload = {
        "data": {
            "matchedUser": {
                "username": "sana",
                "profile": {"ranking": 12345},
                "submitStatsGlobal": {
                    "acSubmissionNum": [
                        {"difficulty": "All", "count": 300},
                        {"difficulty": "Easy", "count": 120},
                        {"difficulty": "Medium", "count": 150},
                        {"difficulty": "Hard", "count": 30},
                    ]
                },
            },
            "userContestRanking": {"rating": 1650.4, "attendedContestsCount": 8, "topPercentage": 20.5},
        }
    }
    with mock.patch.object(clients, "_request", return_value=payload):
        stats = clients.fetch_leetcode("sana")
    assert (stats["solved_total"], stats["solved_medium"], stats["contest_rating"]) == (300, 150, 1650)
    with mock.patch.object(clients, "_request", return_value={"data": {"matchedUser": None}}):
        with pytest.raises(clients.ProfileNotFound):
            clients.fetch_leetcode("nobody")


def _sync_with(student, platform, username, stats):
    profile = CodingProfile.objects.create(
        institution_id=student.institution_id, student=student, platform=platform, username=username
    )
    target = "fetch_github" if platform == "github" else "fetch_leetcode"
    with mock.patch.object(clients, target, return_value=stats):
        services.sync(profile)
    profile.refresh_from_db()
    return profile


def test_sync_records_rating_and_unverified_evidence(make_student, taxonomy):
    student = make_student()
    profile = _sync_with(student, "leetcode", "sana", LEETCODE_STATS)
    assert profile.status == SyncStatus.OK and float(profile.score) > 0
    item = profile.evidence
    assert item.source_type == SourceType.LEETCODE
    assert item.verification_status == VerificationStatus.SELF_REPORTED
    assert item.skill_tags.get().claimed_level == Level.ADVANCED
    recompute_profile(student)
    # 300 problems is evidence, not expertise: unverified external activity is capped at Beginner.
    assert SkillClaim.objects.get(student=student, skill=taxonomy("DSA")).level == Level.BEGINNER


def test_resync_updates_the_same_evidence_item(make_student, taxonomy):
    student = make_student()
    profile = _sync_with(student, "github", "sana-dev", GITHUB_STATS)
    first = profile.evidence_id
    with mock.patch.object(clients, "fetch_github", return_value={**GITHUB_STATS, "recent_push_events": 2}):
        services.sync(profile)
    profile.refresh_from_db()
    assert profile.evidence_id == first
    assert {t.skill.name for t in profile.evidence.skill_tags.select_related("skill")} >= {"Python", "TypeScript"}


def test_not_found_and_errors_are_reported_without_losing_good_data(make_student, taxonomy):
    student = make_student()
    profile = _sync_with(student, "github", "sana-dev", GITHUB_STATS)
    good = profile.score
    with mock.patch.object(clients, "fetch_github", side_effect=clients.FetchError("HTTP 403")):
        services.sync(profile)
    profile.refresh_from_db()
    assert profile.status == SyncStatus.ERROR and profile.score == good
    with mock.patch.object(clients, "fetch_github", side_effect=clients.ProfileNotFound):
        services.sync(profile)
    profile.refresh_from_db()
    assert profile.status == SyncStatus.NOT_FOUND and profile.score is None


def test_coding_activity_is_its_own_readiness_dimension(make_student, taxonomy):
    student = make_student()
    _sync_with(student, "github", "sana-dev", GITHUB_STATS)
    _sync_with(student, "leetcode", "sana", LEETCODE_STATS)
    gh, _ = rating.github_rating(GITHUB_STATS)
    lc, _ = rating.leetcode_rating(LEETCODE_STATS)
    snap = compute_general_snapshot(student)
    assert float(snap.coding_activity) == pytest.approx((gh + lc) / 2, abs=0.02)
    assert snap.explanation["weights"]["coding_activity"] == 10
    assert len(snap.explanation["dimensions"]["coding_activity"]["inputs"]) == 2


def test_api_set_profiles_schedules_sync_and_others_cannot(make_student, as_user, django_capture_on_commit_callbacks):
    student, other = make_student(), make_student()
    with mock.patch("apps.coding.tasks.sync_coding_profile.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            response = as_user(student.user).post(
                "/api/v1/students/me/coding/",
                {"github_username": "sana-dev", "leetcode_username": "sana"},
                format="json",
            )
    assert response.status_code == 200, response.content
    assert delay.call_count == 2
    assert {p["platform"] for p in response.json()["profiles"]} == {"github", "leetcode"}
    assert as_user(other.user).get(f"/api/v1/students/{student.pk}/coding/").status_code == 404
    assert (
        as_user(student.user)
        .post("/api/v1/students/me/coding/", {"github_username": "bad user!"}, format="json")
        .status_code
        == 400
    )


def test_mentor_and_officer_can_read_ratings(make_student, faculty, officer, as_user, taxonomy):
    student = make_student()
    _sync_with(student, "github", "sana-dev", GITHUB_STATS)
    for user in (faculty, officer):
        body = as_user(user).get(f"/api/v1/students/{student.pk}/coding/").json()
        assert body["coding_activity"] is not None
