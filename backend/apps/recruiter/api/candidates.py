"""Layer 2 of recruiter protection: a candidate is serialized field by field from the grant's
allow-list. A field that is not both in RELEASABLE_FIELDS and in the grant is never emitted."""

from apps.evidence.models import EvidenceItem
from apps.matching.models import MatchResult
from apps.profiles.models import SkillClaim
from apps.readiness.models import ReadinessSnapshot
from apps.recruiter.models import RELEASABLE_FIELDS
from apps.taxonomy.models import Level


def released_fields(grant):
    return [f for f in grant.allowed_fields if f in RELEASABLE_FIELDS]


def load_context(grant, students, *, detail):
    ids = [s.pk for s in students]
    fields = set(released_fields(grant))
    ctx = {"fields": fields, "detail": detail}
    if "compatibility" in fields:
        ctx["compatibility"] = dict(
            MatchResult.objects.filter(drive_id=grant.drive_id, student_id__in=ids).values_list(
                "student_id", "compatibility"
            )
        )
    if "readiness" in fields:
        ctx["readiness"] = {}
        for snap in (
            ReadinessSnapshot.objects.filter(drive_id=grant.drive_id, student_id__in=ids)
            .order_by("student_id", "-created_at", "-id")
            .distinct("student_id")
        ):
            ctx["readiness"][snap.student_id] = snap
    if "skills" in fields:
        ctx["skills"] = {}
        for c in SkillClaim.objects.filter(student_id__in=ids).select_related("skill").order_by("-level"):
            ctx["skills"].setdefault(c.student_id, []).append(c)
    if "evidence" in fields and detail:
        ctx["evidence"] = {}
        for e in EvidenceItem.objects.filter(student_id__in=ids).exclude(verification_status="rejected"):
            ctx["evidence"].setdefault(e.student_id, []).append(e)
    if "coding_activity" in fields:
        from apps.coding.services import coding_activity

        ctx["coding"] = coding_activity(ids)
    if "resume" in fields:
        from apps.students.models import StudentResume

        ctx["resume"] = set(
            StudentResume.objects.filter(student_id__in=ids, is_current=True).values_list("student_id", flat=True)
        )
    if "registration_status" in fields:
        ctx["registration"] = dict(
            grant.drive.registrations.filter(student_id__in=ids).values_list("student_id", "status")
        )
    return ctx


def serialize_candidate(student, ctx):
    f = ctx["fields"]
    data = {"id": student.pk}
    if "name" in f:
        data["name"] = student.name
    if "email" in f:
        data["email"] = student.user.email
    if "department" in f:
        data["department"] = {"code": student.department.code, "name": student.department.name}
    if "graduation_year" in f:
        data["graduation_year"] = student.graduation_year
    if "cgpa" in f:
        data["cgpa"] = str(student.cgpa)
    if "compatibility" in f:
        value = ctx["compatibility"].get(student.pk)
        data["compatibility"] = float(value) if value is not None else None
    if "readiness" in f:
        snap = ctx["readiness"].get(student.pk)
        data["readiness"] = (
            None
            if snap is None
            else {
                "overall": float(snap.overall),
                "technical": float(snap.technical),
                "aptitude": float(snap.aptitude),
                "communication": float(snap.communication),
                "project_depth": float(snap.project_depth),
                "coding_activity": float(snap.coding_activity),
            }
        )
    if "skills" in f:
        claims = ctx["skills"].get(student.pk, [])
        limit = None if ctx["detail"] else 5
        data["skills"] = [
            {"skill": c.skill.name, "level": Level(c.level).label, "verified": c.is_verified} for c in claims[:limit]
        ]
    if "evidence" in f and ctx["detail"]:
        data["evidence"] = [
            {"title": e.title, "type": e.get_source_type_display(), "verification": e.get_verification_status_display()}
            for e in ctx["evidence"].get(student.pk, [])
        ]
    if "registration_status" in f:
        data["registration_status"] = ctx["registration"].get(student.pk)
    if "coding_activity" in f:
        score, profiles = ctx["coding"].get(student.pk, (None, []))
        data["coding_activity"] = {
            "score": score,
            "platforms": [
                {"platform": p.get_platform_display(), "rating": float(p.score) if p.score is not None else None}
                for p in profiles
            ],
        }
    if "resume" in f:
        data["resume_available"] = student.pk in ctx["resume"]
    return data
