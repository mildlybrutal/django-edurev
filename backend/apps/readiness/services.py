from collections import defaultdict

from django.db import transaction
from django.db.models import Max

from apps.assessments.models import Assessment, AssessmentKind, MockInterview
from apps.evidence.models import EvidenceItem, SourceType, VerificationStatus
from apps.profiles.models import SkillClaim
from apps.taxonomy.models import Level

from .models import ReadinessSnapshot, ScoringConfig
from .policy import MAX_LEVEL, credited_level, q2, weighted_overall


class ReadinessError(ValueError):
    pass


def active_config(institution_id):
    config = ScoringConfig.objects.filter(institution_id=institution_id, is_active=True).first()
    if config is None:
        config, _ = ScoringConfig.objects.get_or_create(
            institution_id=institution_id, version=1, defaults={"is_active": True}
        )
    return config


@transaction.atomic
def publish_config(*, institution, created_by, **values):
    """Create a new active config version; the previous version stays for old snapshots."""
    weights = [
        values.get(k, 0)
        for k in (
            "weight_technical",
            "weight_aptitude",
            "weight_communication",
            "weight_project_depth",
            "weight_coding",
        )
    ]
    if sum(weights) <= 0:
        raise ReadinessError("At least one dimension weight must be positive.")
    current = active_config(institution.id)
    fields = {
        f: getattr(current, f)
        for f in (
            "weight_technical",
            "weight_aptitude",
            "weight_communication",
            "weight_project_depth",
            "weight_coding",
            "unverified_multiplier",
            "technical_top_n",
            "recent_window",
            "project_target",
            "ready_threshold",
        )
    }
    fields.update(values)
    latest = ScoringConfig.objects.filter(institution=institution).aggregate(v=Max("version"))["v"] or 0
    ScoringConfig.objects.filter(institution=institution, is_active=True).update(is_active=False)
    return ScoringConfig.objects.create(
        institution=institution, version=latest + 1, is_active=True, created_by=created_by, **fields
    )


def _load_inputs(student_ids, config):
    claims = defaultdict(list)
    for c in SkillClaim.objects.filter(student_id__in=student_ids).select_related("skill"):
        claims[c.student_id].append(c)

    aptitude = defaultdict(list)
    communication = defaultdict(list)
    for a in Assessment.objects.filter(student_id__in=student_ids).order_by("-assessed_on", "-id"):
        item = {
            "source": "assessment",
            "title": a.title,
            "date": a.assessed_on.isoformat(),
            "score": float(a.percentage),
        }
        if a.kind == AssessmentKind.APTITUDE:
            aptitude[a.student_id].append(item)
        elif a.kind == AssessmentKind.COMMUNICATION:
            communication[a.student_id].append(item)
    for m in MockInterview.objects.filter(student_id__in=student_ids).order_by("-conducted_on", "-id"):
        communication[m.student_id].append(
            {
                "source": "mock_interview",
                "title": "Mock interview",
                "date": m.conducted_on.isoformat(),
                "score": float(m.communication_score),
            }
        )
    for items in communication.values():
        items.sort(key=lambda i: i["date"], reverse=True)

    projects = defaultdict(list)
    for p in (
        EvidenceItem.objects.filter(student_id__in=student_ids, source_type=SourceType.PROJECT)
        .exclude(verification_status=VerificationStatus.REJECTED)
        .prefetch_related("skill_tags")
    ):
        projects[p.student_id].append(p)
    return claims, aptitude, communication, projects


def _recent_average(items, window):
    used = items[:window]
    if not used:
        return 0.0, used
    return sum(i["score"] for i in used) / len(used), used


def general_technical(claims, config):
    """Mean credited level of the student's strongest skills, as % of Expert."""
    m = config.unverified_multiplier
    scored = sorted(
        (
            {
                "skill": c.skill.name,
                "level": Level(c.level).label,
                "verified_level": Level(c.verified_level).label,
                "credited": round(credited_level(c.level, c.verified_level, m), 2),
            }
            for c in claims
            if not c.skill.is_abstract
        ),
        key=lambda x: -x["credited"],
    )[: config.technical_top_n]
    if not scored:
        return 0.0, {"summary": "No skill evidence yet.", "inputs": [], "missing": "Add evidence tagged with skills."}
    score = 100 * sum(s["credited"] for s in scored) / (len(scored) * MAX_LEVEL)
    return score, {
        "summary": f"Average credited level of your top {len(scored)} skills (unverified evidence counts at "
        f"{float(m):.0%}).",
        "inputs": scored,
        "missing": None,
    }


def project_depth(projects, config):
    m = float(config.unverified_multiplier)
    inputs, points = [], 0.0
    for p in projects:
        weight = 1.0 if p.verification_status == VerificationStatus.VERIFIED else m
        breadth = min(len(p.skill_tags.all()), 3) / 3
        inputs.append(
            {
                "title": p.title,
                "verified": weight == 1.0,
                "skills": len(p.skill_tags.all()),
                "points": round(weight * breadth, 2),
            }
        )
        points += weight * breadth
    score = min(1.0, points / config.project_target) * 100 if config.project_target else 0.0
    missing = None if projects else "Add a project with the skills it used."
    return score, {
        "summary": f"{len(projects)} project(s); {config.project_target} verified projects using 3+ skills each "
        f"give full marks.",
        "inputs": inputs,
        "missing": missing,
    }


_NO_CODING = {
    "summary": "Mean of your synced GitHub, LeetCode and Codeforces ratings (unverified external activity).",
    "inputs": [],
    "missing": "Link your GitHub, LeetCode or Codeforces profiles to add coding activity.",
}


def _coding_inputs(student_ids):
    """{student_id: (score, explanation)} for students with at least one synced platform rating."""
    from apps.coding.services import coding_activity

    result = {}
    for sid, (score, profiles) in coding_activity(student_ids).items():
        rows = [
            {
                "platform": p.get_platform_display(),
                "username": p.username,
                "rating": float(p.score) if p.score is not None else None,
                "status": p.get_status_display(),
            }
            for p in profiles
        ]
        result[sid] = (
            score or 0.0,
            {
                "summary": "Mean of your synced GitHub, LeetCode and Codeforces ratings. Public activity is "
                "unverified external evidence: it supports, but never proves, expertise.",
                "inputs": rows,
                "missing": None if score is not None else "None of your coding profiles has synced yet.",
            },
        )
    return result


def compute_snapshots(students, *, drive=None, technical_by_student=None):
    """Compute and store one snapshot per student. For a drive, `technical_by_student` maps
    student id -> (score, explanation) from the matching engine; otherwise the general technical
    score is used. Bulk-friendly: a fixed number of queries regardless of cohort size."""
    students = list(students)
    if not students:
        return []
    configs = {}
    ids = [s.pk for s in students]
    claims, aptitude, communication, projects = _load_inputs(ids, None)
    coding = _coding_inputs(ids)
    snapshots = []
    for s in students:
        config = configs.get(s.institution_id) or configs.setdefault(s.institution_id, active_config(s.institution_id))
        if technical_by_student is not None:
            tech, tech_exp = technical_by_student[s.pk]
        else:
            tech, tech_exp = general_technical(claims[s.pk], config)
        apt, apt_used = _recent_average(aptitude[s.pk], config.recent_window)
        com, com_used = _recent_average(communication[s.pk], config.recent_window)
        proj, proj_exp = project_depth(projects[s.pk], config)
        code, code_exp = coding.get(s.pk, (0.0, _NO_CODING))
        scores = {
            "technical": tech,
            "aptitude": apt,
            "communication": com,
            "project_depth": proj,
            "coding_activity": code,
        }
        overall = weighted_overall(scores, config.weights)
        explanation = {
            "config_version": config.version,
            "weights": config.weights,
            "ready_threshold": config.ready_threshold,
            "dimensions": {
                "technical": {"score": round(tech, 2), **tech_exp},
                "aptitude": {
                    "score": round(apt, 2),
                    "summary": f"Average of your latest {config.recent_window} aptitude assessments.",
                    "inputs": apt_used,
                    "missing": None if apt_used else "No aptitude assessment recorded yet.",
                },
                "communication": {
                    "score": round(com, 2),
                    "summary": f"Average of your latest {config.recent_window} communication assessments and "
                    f"mock-interview communication scores.",
                    "inputs": com_used,
                    "missing": None if com_used else "No communication assessment or mock interview yet.",
                },
                "project_depth": {"score": round(proj, 2), **proj_exp},
                "coding_activity": {"score": round(code, 2), **code_exp},
            },
            "note": "Missing evidence scores 0: readiness reflects only what has been demonstrated.",
        }
        snapshots.append(
            ReadinessSnapshot(
                institution_id=s.institution_id,
                student=s,
                drive=drive,
                config=config,
                technical=q2(tech),
                aptitude=q2(apt),
                communication=q2(com),
                project_depth=q2(proj),
                coding_activity=q2(code),
                overall=q2(overall),
                explanation=explanation,
            )
        )
    return ReadinessSnapshot.objects.bulk_create(snapshots, batch_size=1000)


def compute_general_snapshot(student):
    return compute_snapshots([student])[0]


def latest_snapshot(student, drive=None):
    return ReadinessSnapshot.objects.filter(student=student, drive=drive).first()


def latest_general_overall(student_ids):
    """{student_id: overall} from each student's most recent general snapshot."""
    rows = (
        ReadinessSnapshot.objects.filter(student_id__in=student_ids, drive__isnull=True)
        .order_by("student_id", "-created_at", "-id")
        .distinct("student_id")
        .values_list("student_id", "overall")
    )
    return {sid: float(overall) for sid, overall in rows}


def is_ready(overall, config):
    return float(overall) >= config.ready_threshold
