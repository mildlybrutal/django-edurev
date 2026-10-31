from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from apps.evidence.models import EvidenceItem, EvidenceSkillTag, SourceType, VerificationStatus
from apps.taxonomy.models import Level

from .models import ClaimEvidence, EvidenceRule, SkillClaim

L = Level
# Implementation defaults (see docs/scoring-policy.md). Key idea: unverified evidence, and
# external platform activity in particular, can never establish more than a low level on its own.
DEFAULT_RULES = {
    SourceType.ACADEMIC: (L.ADVANCED, L.ADVANCED),
    SourceType.PROJECT: (L.INTERMEDIATE, L.EXPERT),
    SourceType.CERTIFICATION: (L.BEGINNER, L.ADVANCED),
    SourceType.ASSESSMENT: (L.EXPERT, L.EXPERT),
    SourceType.MOCK_INTERVIEW: (L.ADVANCED, L.ADVANCED),
    SourceType.GITHUB: (L.BEGINNER, L.ADVANCED),
    SourceType.LEETCODE: (L.BEGINNER, L.ADVANCED),
    SourceType.CODECHEF: (L.BEGINNER, L.ADVANCED),
    SourceType.CODEFORCES: (L.BEGINNER, L.ADVANCED),
    SourceType.OTHER: (L.BEGINNER, L.INTERMEDIATE),
}


def ensure_default_rules(institution_id):
    existing = set(EvidenceRule.objects.filter(institution_id=institution_id).values_list("source_type", flat=True))
    EvidenceRule.objects.bulk_create(
        EvidenceRule(institution_id=institution_id, source_type=st, max_level_unverified=u, max_level_verified=v)
        for st, (u, v) in DEFAULT_RULES.items()
        if st not in existing
    )


def rules_for(institution_id):
    ensure_default_rules(institution_id)
    return {r.source_type: r for r in EvidenceRule.objects.filter(institution_id=institution_id)}


def effective_level(rule, claimed_level, verified):
    cap = rule.max_level_verified if verified else rule.max_level_unverified
    return min(claimed_level, cap)


def build_claims(students):
    """Recompute skill claims for the given students from their current evidence.

    Rejected evidence is ignored. Each tag's claimed level is capped by its source rule
    (lower cap when unverified). A claim's level is the best effective level across evidence;
    its verified_level is the best from verified evidence only, so the gap between the two stays
    visible instead of being silently trusted.
    """
    students = list(students)
    if not students:
        return
    by_institution = defaultdict(list)
    for s in students:
        by_institution[s.institution_id].append(s)
    for institution_id, group in by_institution.items():
        rules = rules_for(institution_id)
        _build_for_group(group, rules)


@transaction.atomic
def _build_for_group(students, rules):
    ids = [s.pk for s in students]
    tags = (
        EvidenceSkillTag.objects.filter(evidence__student_id__in=ids)
        .exclude(evidence__verification_status=VerificationStatus.REJECTED)
        .filter(skill__is_active=True)
        .select_related("evidence")
        .values_list(
            "evidence__student_id",
            "skill_id",
            "claimed_level",
            "evidence_id",
            "evidence__source_type",
            "evidence__verification_status",
            "evidence__institution_id",
        )
    )
    grouped = defaultdict(list)
    for student_id, skill_id, claimed, evidence_id, source, status, _ in tags:
        verified = status == VerificationStatus.VERIFIED
        grouped[(student_id, skill_id)].append(
            (evidence_id, claimed, effective_level(rules[source], claimed, verified), verified)
        )

    SkillClaim.objects.filter(student_id__in=ids).delete()
    institution_of = {s.pk: s.institution_id for s in students}
    claims = []
    for (student_id, skill_id), supports in grouped.items():
        level = max(eff for _, _, eff, _ in supports)
        verified_level = max((eff for _, _, eff, v in supports if v), default=Level.NONE)
        claims.append(
            SkillClaim(
                institution_id=institution_of[student_id],
                student_id=student_id,
                skill_id=skill_id,
                level=level,
                verified_level=verified_level,
                evidence_count=len(supports),
            )
        )
    SkillClaim.objects.bulk_create(claims, batch_size=2000)
    claim_ids = {
        (c.student_id, c.skill_id): c.pk
        for c in SkillClaim.objects.filter(student_id__in=ids).only("id", "student_id", "skill_id")
    }
    ClaimEvidence.objects.bulk_create(
        (
            ClaimEvidence(
                claim_id=claim_ids[key], evidence_id=eid, claimed_level=claimed, effective_level=eff, verified=v
            )
            for key, supports in grouped.items()
            for eid, claimed, eff, v in supports
        ),
        batch_size=5000,
    )


def recompute_profile(student):
    build_claims([student])


def schedule_recompute(student_id):
    """Debounced recompute: the first change in a window schedules one task; further changes in
    the same window are absorbed by it (P06 §8: 'readiness recomputation ... debounced')."""
    from .tasks import recompute_student

    delay = getattr(settings, "PROFILE_RECOMPUTE_DEBOUNCE_SECONDS", 30)
    if cache.add(f"profile-recompute:{student_id}", 1, timeout=delay):
        transaction.on_commit(lambda: recompute_student.apply_async(args=[student_id], countdown=delay))
        return True
    return False


PROFILE_CHECKS = [
    ("headline", "Add a profile headline"),
    ("project", "Add at least one project"),
    ("four_types", "Have evidence from at least four different sources"),
    ("verified", "Get at least one item verified by your mentor"),
    ("assessment", "Take an institutional assessment"),
    ("mock_interview", "Complete a mock interview"),
    ("resume", "Upload your resume"),
    ("coding", "Link your GitHub or LeetCode profile"),
]


def profile_completion(student):
    items = list(EvidenceItem.objects.filter(student=student).values_list("source_type", "verification_status"))
    sources = {s for s, _ in items}
    done = {
        "headline": bool(student.headline),
        "project": SourceType.PROJECT in sources,
        "four_types": len(sources) >= 4,
        "verified": any(v == VerificationStatus.VERIFIED for _, v in items),
        "assessment": SourceType.ASSESSMENT in sources,
        "mock_interview": SourceType.MOCK_INTERVIEW in sources,
        "resume": student.resumes.filter(is_current=True).exists(),
        "coding": student.coding_profiles.exists(),
    }
    checks = [{"key": k, "label": label, "done": done[k]} for k, label in PROFILE_CHECKS]
    return {"percent": round(100 * sum(done.values()) / len(done)), "checks": checks}
