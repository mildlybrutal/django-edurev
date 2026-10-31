from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.core.models import BackgroundJob
from apps.drives import services as drive_services
from apps.drives.models import Drive
from apps.notifications.services import notify
from apps.profiles.models import SkillClaim
from apps.readiness import services as readiness_services
from apps.readiness.policy import q2
from apps.students.models import StudentProfile
from apps.taxonomy.models import Skill, SkillClosure

from . import scoring
from .models import GapAnalysis, GapItem, MatchResult

CHUNK_SIZE = 500


class DriveContext:
    """Everything about a drive needed to score students, loaded once."""

    def __init__(self, drive):
        self.drive = drive
        self.requirements = list(drive.requirements.select_related("skill"))
        req_ids = [r.skill_id for r in self.requirements]
        self.satisfying = defaultdict(set)
        self.depth = defaultdict(dict)
        for ancestor, descendant, depth in SkillClosure.objects.filter(ancestor_id__in=req_ids).values_list(
            "ancestor_id", "descendant_id", "depth"
        ):
            self.satisfying[ancestor].add(descendant)
            self.depth[ancestor][descendant] = depth
        # Concrete examples for abstract requirements, used in gap suggestions.
        names = dict(
            Skill.objects.filter(is_active=True, pk__in={d for s in self.satisfying.values() for d in s}).values_list(
                "pk", "name"
            )
        )
        self.examples = {
            r.skill_id: [
                names[d]
                for d, depth in sorted(self.depth[r.skill_id].items(), key=lambda kv: kv[1])
                if depth > 0 and d in names
            ][:3]
            for r in self.requirements
        }
        self.config = readiness_services.active_config(drive.institution_id)

    def breakdown(self, claims_by_skill):
        m = self.config.unverified_multiplier
        return [
            scoring.score_requirement(r, claims_by_skill, self.satisfying[r.skill_id], self.depth[r.skill_id], m)
            for r in self.requirements
        ]


def _claims_for(student_ids):
    claims = defaultdict(dict)
    for c in SkillClaim.objects.filter(student_id__in=student_ids).select_related("skill"):
        claims[c.student_id][c.skill_id] = c
    return claims


@transaction.atomic
def match_chunk(context, students):
    """Eligibility, compatibility, drive readiness and gaps for a chunk of students."""
    drive = context.drive
    eligibility = drive_services.evaluate_and_store(drive, students)
    claims = _claims_for([s.pk for s in students])

    breakdowns, technical = {}, {}
    for s in students:
        bd = context.breakdown(claims[s.pk])
        score = scoring.compatibility(bd)
        breakdowns[s.pk] = (bd, score)
        technical[s.pk] = (score, scoring.technical_explanation(bd, score, context.config.unverified_multiplier))

    snapshots = readiness_services.compute_snapshots(students, drive=drive, technical_by_student=technical)
    snapshot_of = {snap.student_id: snap for snap in snapshots}

    MatchResult.objects.bulk_create(
        [
            MatchResult(
                institution_id=drive.institution_id,
                drive=drive,
                student=s,
                compatibility=q2(breakdowns[s.pk][1]),
                breakdown=breakdowns[s.pk][0],
                readiness_overall=snapshot_of[s.pk].overall,
                readiness_snapshot=snapshot_of[s.pk],
            )
            for s in students
        ],
        update_conflicts=True,
        unique_fields=["drive", "student"],
        update_fields=["compatibility", "breakdown", "readiness_overall", "readiness_snapshot", "computed_at"],
        batch_size=1000,
    )
    GapAnalysis.objects.bulk_create(
        [GapAnalysis(institution_id=drive.institution_id, drive=drive, student=s) for s in students],
        update_conflicts=True,
        unique_fields=["drive", "student"],
        update_fields=["computed_at"],
        batch_size=1000,
    )
    analysis_ids = dict(GapAnalysis.objects.filter(drive=drive, student__in=students).values_list("student_id", "pk"))
    GapItem.objects.filter(analysis_id__in=analysis_ids.values()).delete()
    GapItem.objects.bulk_create(
        [
            GapItem(analysis_id=analysis_ids[s.pk], **{k: v for k, v in g.items() if k != "skill"})
            for s in students
            for g in scoring.gaps(breakdowns[s.pk][0], context.examples)
        ],
        batch_size=5000,
    )
    return {s.pk: (eligibility[s.pk][0], breakdowns[s.pk][1], snapshot_of[s.pk]) for s in students}


def match_student(drive, student):
    """On-demand evaluation for one student (e.g. when they open a drive)."""
    return match_chunk(DriveContext(drive), [student])[student.pk]


def drive_population(drive):
    return StudentProfile.objects.filter(institution_id=drive.institution_id).select_related("department", "user")


def run_drive_matching(drive, *, job=None, notify_students=False):
    context = DriveContext(drive)
    students = list(drive_population(drive))
    if job is not None:
        job.total = len(students)
        job.save(update_fields=["total"])
    summary = {"students": len(students), "eligible": 0, "compatibility_sum": 0.0}
    for start in range(0, len(students), CHUNK_SIZE):
        chunk = students[start : start + CHUNK_SIZE]
        results = match_chunk(context, chunk)
        for student in chunk:
            eligible, compat, _ = results[student.pk]
            summary["eligible"] += int(eligible)
            summary["compatibility_sum"] += compat
            if notify_students:
                _notify_student(drive, student, eligible, compat)
        if job is not None:
            job.processed = min(start + CHUNK_SIZE, len(students))
            job.save(update_fields=["processed"])
    drive.last_matched_at = timezone.now()
    drive.save(update_fields=["last_matched_at", "updated_at"])
    avg = summary["compatibility_sum"] / len(students) if students else 0.0
    return {"students": len(students), "eligible": summary["eligible"], "average_compatibility": round(avg, 2)}


def _notify_student(drive, student, eligible, compat):
    if eligible:
        notify(
            student.user,
            kind="new_drive_match",
            title=f"New drive: {drive} — {compat:.0f}% skill match",
            body="You meet the eligibility criteria. Open the drive to see your gaps and register.",
            link=f"/student/drives/{drive.pk}",
        )
    else:
        reasons = drive.eligibility_results.filter(student=student).values_list("reasons", flat=True).first() or []
        missed = "; ".join(r["message"] for r in reasons if not r["passed"])
        notify(
            student.user,
            kind="eligibility_missed",
            title=f"Not eligible for {drive}",
            body=missed,
            link=f"/student/drives/{drive.pk}",
        )


def start_drive_matching_job(drive, *, created_by=None, notify_students=False):
    from .tasks import run_drive_matching_task

    job = BackgroundJob.objects.create(
        institution_id=drive.institution_id,
        kind="drive_matching",
        params={"drive_id": drive.pk},
        created_by=created_by,
    )
    transaction.on_commit(
        lambda: run_drive_matching_task.delay(drive.pk, job_id=job.pk, notify_students=notify_students)
    )
    return job


def results_for_drive(drive):
    return MatchResult.objects.filter(drive=drive).select_related("student__user", "student__department")


def drive_for_student(drive_id, student):
    return Drive.objects.filter(pk=drive_id, institution_id=student.institution_id).first()
