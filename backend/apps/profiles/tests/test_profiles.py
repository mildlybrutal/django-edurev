from unittest import mock

import pytest

from apps.evidence import services as ev
from apps.evidence.models import SourceType, VerificationStatus
from apps.profiles import services
from apps.profiles.models import SkillClaim
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(make_student):
    return make_student(name="Alice")


def claim(student, skill):
    return SkillClaim.objects.get(student=student, skill=skill)


def test_profile_assembled_from_four_evidence_types_with_status(alice, taxonomy, give_evidence, faculty, as_user):
    give_evidence(alice, SourceType.PROJECT, "Shop API", [(taxonomy("Django"), Level.INTERMEDIATE)], verified=True)
    give_evidence(alice, SourceType.CERTIFICATION, "AWS CCP", [(taxonomy("AWS"), Level.BEGINNER)])
    give_evidence(alice, SourceType.LEETCODE, "LeetCode", [(taxonomy("DSA"), Level.ADVANCED)])
    give_evidence(alice, SourceType.ASSESSMENT, "Python test", [(taxonomy("Python"), Level.ADVANCED)], recorder=faculty)

    body = as_user(alice.user).get("/api/v1/students/me/profile/").json()
    by_skill = {c["skill"]: c for c in body["claims"]}
    assert set(by_skill) == {"Django", "AWS", "Data Structures & Algorithms", "Python"}
    sources = {e["source_type"] for c in body["claims"] for e in c["evidence"]}
    assert sources == {"project", "certification", "leetcode", "assessment"}
    # Verification status is visible on every supporting item.
    assert by_skill["Django"]["evidence"][0]["verification_status"] == "verified"
    assert by_skill["AWS"]["evidence"][0]["verification_status"] == "self_reported"
    assert body["completion"]["checks"][2] == {"key": "four_types", "label": mock.ANY, "done": True}


def test_external_platform_activity_is_not_automatic_expertise(alice, taxonomy, give_evidence):
    """'500 LeetCode problems = Expert DSA' must not happen without verification (AGENTS.md §3)."""
    dsa = taxonomy("DSA")
    give_evidence(alice, SourceType.LEETCODE, "500 problems solved", [(dsa, Level.EXPERT)])
    c = claim(alice, dsa)
    assert c.level == Level.BEGINNER
    assert c.verified_level == Level.NONE
    assert not c.is_verified


def test_verification_raises_the_supported_level(alice, taxonomy, give_evidence):
    django = taxonomy("Django")
    item = give_evidence(alice, SourceType.PROJECT, "Shop", [(django, Level.EXPERT)])
    assert claim(alice, django).level == Level.INTERMEDIATE  # unverified project cap
    ev.set_status(item, VerificationStatus.VERIFIED)
    services.recompute_profile(alice)
    c = claim(alice, django)
    assert (c.level, c.verified_level, c.is_verified) == (Level.EXPERT, Level.EXPERT, True)


def test_rejected_evidence_is_ignored(alice, taxonomy, give_evidence):
    docker = taxonomy("Docker")
    item = give_evidence(alice, SourceType.PROJECT, "Containers", [(docker, Level.INTERMEDIATE)])
    ev.set_status(item, VerificationStatus.REJECTED)
    services.recompute_profile(alice)
    assert not SkillClaim.objects.filter(student=alice, skill=docker).exists()


def test_claim_keeps_provenance_from_every_item(alice, taxonomy, give_evidence):
    python = taxonomy("Python")
    give_evidence(alice, SourceType.PROJECT, "A", [(python, Level.INTERMEDIATE)], verified=True)
    give_evidence(alice, SourceType.GITHUB, "B", [(python, Level.ADVANCED)])
    c = claim(alice, python)
    assert c.evidence_count == 2
    assert {s.evidence.title for s in c.supports.select_related("evidence")} == {"A", "B"}
    assert c.level == Level.INTERMEDIATE and c.verified_level == Level.INTERMEDIATE


def test_evidence_rules_are_configurable(alice, taxonomy, give_evidence):
    from apps.profiles.models import EvidenceRule

    services.ensure_default_rules(alice.institution_id)
    EvidenceRule.objects.filter(source_type=SourceType.GITHUB).update(max_level_unverified=Level.INTERMEDIATE)
    give_evidence(alice, SourceType.GITHUB, "Repo", [(taxonomy("Python"), Level.ADVANCED)])
    assert claim(alice, taxonomy("Python")).level == Level.INTERMEDIATE


def test_recompute_is_debounced(alice, django_capture_on_commit_callbacks):
    with mock.patch("apps.profiles.tasks.recompute_student.apply_async") as apply_async:
        with django_capture_on_commit_callbacks(execute=True):
            assert services.schedule_recompute(alice.pk) is True
            assert services.schedule_recompute(alice.pk) is False
            assert services.schedule_recompute(alice.pk) is False
    apply_async.assert_called_once()
    assert apply_async.call_args.kwargs["countdown"] >= 1


def test_new_evidence_triggers_profile_and_readiness_recompute(alice, taxonomy, django_capture_on_commit_callbacks):
    from apps.readiness.models import ReadinessSnapshot

    with django_capture_on_commit_callbacks(execute=True):
        ev.submit_evidence(
            student=alice, source_type=SourceType.PROJECT, title="API", tags=[(taxonomy("Django"), Level.INTERMEDIATE)]
        )
    # Eager Celery in tests runs the scheduled task immediately.
    assert SkillClaim.objects.filter(student=alice).exists()
    assert ReadinessSnapshot.objects.filter(student=alice, drive__isnull=True).exists()


def test_skill_merge_repoints_evidence_tags(alice, institution, give_evidence):
    from apps.taxonomy.services import create_skill, merge_skills

    old = create_skill(institution=institution, name="Postgres SQL")
    new = create_skill(institution=institution, name="PostgreSQL")
    give_evidence(alice, SourceType.PROJECT, "DB work", [(old, Level.BEGINNER)])
    merge_skills(old, new)
    services.recompute_profile(alice)
    assert SkillClaim.objects.filter(student=alice, skill=new).exists()
    assert not SkillClaim.objects.filter(student=alice, skill=old).exists()
