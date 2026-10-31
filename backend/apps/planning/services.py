from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.matching.models import GapAnalysis, GapKind
from apps.notifications.services import notify
from apps.taxonomy.models import Level

from .models import ItemStatus, LearningResource, PlanItem, PlanStatus, PreparationPlan


class PlanError(ValueError):
    pass


DEFAULT_HORIZON_DAYS = 28
MIN_DAYS_PER_GAP = 3


def _days_needed(gap):
    """Rough effort per gap: a week per level to climb, two days for a verification-only gap.
    Implementation heuristic, scaled down when the drive date leaves less time."""
    if gap.kind == GapKind.UNVERIFIED:
        return 2
    return 7 * max(1, gap.required_level - gap.current_level)


def _resource(gap):
    return (
        LearningResource.objects.filter(skill_id=gap.skill_id, target_level__lte=gap.required_level)
        .order_by("-target_level")
        .first()
    )


def _items_for_gap(gap, start, end, order):
    skill = gap.skill.name
    req = Level(gap.required_level).label
    resource = _resource(gap) if gap.kind != GapKind.UNVERIFIED else None
    span = (end - start).days
    items = []
    if gap.kind == GapKind.UNVERIFIED:
        items.append(
            dict(
                title=f"Request verification of your {skill} evidence",
                description="Send your strongest evidence to your mentor, or book an institutional assessment.",
                start_date=start,
                due_date=start + timedelta(days=max(0, span - 1)),
            )
        )
    else:
        learn_end = start + timedelta(days=max(0, span // 2 - 1))
        items.append(
            dict(
                title=f"Learn {skill} towards {req}",
                description=gap.suggested_action,
                resource_title=resource.title if resource else "",
                resource_url=resource.url if resource else "",
                start_date=start,
                due_date=learn_end,
            )
        )
        items.append(
            dict(
                title=f"Apply {skill} in a project or practice set",
                description=f"Build something that uses {skill} at {req} level and add it as evidence.",
                start_date=learn_end + timedelta(days=1) if span > 1 else start,
                due_date=end,
            )
        )
    items.append(
        dict(
            title=f"Checkpoint: {skill} at {req}",
            description="Evidence added and verification requested. Your readiness updates automatically.",
            start_date=end,
            due_date=end,
            is_checkpoint=True,
        )
    )
    return [PlanItem(skill_id=gap.skill_id, order=order + i, **item) for i, item in enumerate(items)]


@transaction.atomic
def generate_plan(student, drive, *, today=None):
    """Turn the student's ranked gaps for a drive into a dated plan ending before the drive."""
    today = today or timezone.localdate()
    analysis = GapAnalysis.objects.filter(student=student, drive=drive).first()
    if analysis is None:
        raise PlanError("Run the gap analysis for this drive first.")
    gaps = list(analysis.items.select_related("skill").order_by("rank"))
    if not gaps:
        raise PlanError("No gaps for this drive — nothing to plan.")

    end = drive.drive_date - timedelta(days=1) if drive.drive_date else today + timedelta(days=DEFAULT_HORIZON_DAYS)
    if end <= today:
        end = today + timedelta(days=MIN_DAYS_PER_GAP)
    available = (end - today).days + 1
    needed = [_days_needed(g) for g in gaps]
    # Highest-impact gaps first; compress proportionally if time is short, but never below a minimum.
    scale = min(1.0, available / sum(needed))
    PreparationPlan.objects.filter(student=student, drive=drive, status=PlanStatus.ACTIVE).update(
        status=PlanStatus.ARCHIVED
    )
    plan = PreparationPlan.objects.create(
        institution_id=student.institution_id,
        student=student,
        drive=drive,
        title=f"Preparation for {drive}",
        start_date=today,
        end_date=end,
    )
    cursor, order, items = today, 0, []
    for gap, days in zip(gaps, needed, strict=True):
        span = max(MIN_DAYS_PER_GAP if gap.kind != GapKind.UNVERIFIED else 1, round(days * scale))
        gap_end = min(cursor + timedelta(days=span - 1), end)
        if cursor > end:
            cursor = gap_end = end
        new_items = _items_for_gap(gap, cursor, gap_end, order)
        for item in new_items:
            item.plan = plan
        items.extend(new_items)
        order += len(new_items)
        cursor = gap_end + timedelta(days=1)
    PlanItem.objects.bulk_create(items)
    return plan


def update_item_status(item, student, status):
    if item.plan.student_id != student.pk:
        raise PlanError("Not your plan.")
    if status not in ItemStatus.values:
        raise PlanError("Unknown status.")
    item.status = status
    item.completed_at = timezone.now() if status == ItemStatus.DONE else None
    item.save(update_fields=["status", "completed_at"])
    return item


def progress(plan):
    items = list(plan.items.all())
    done = sum(i.status == ItemStatus.DONE for i in items)
    today = timezone.localdate()
    overdue = sum(i.status != ItemStatus.DONE and i.due_date < today for i in items)
    return {
        "total": len(items),
        "done": done,
        "overdue": overdue,
        "percent": round(100 * done / len(items)) if items else 0,
    }


def send_checkpoint_reminders(today=None):
    """Daily (Celery Beat): remind students of checkpoints due tomorrow."""
    today = today or timezone.localdate()
    due = (
        PlanItem.objects.filter(
            is_checkpoint=True,
            due_date=today + timedelta(days=1),
            reminder_sent_at__isnull=True,
            plan__status=PlanStatus.ACTIVE,
        )
        .exclude(status=ItemStatus.DONE)
        .select_related("plan__student__user")
    )
    count = 0
    for item in due:
        notify(
            item.plan.student.user,
            kind="checkpoint_due",
            title=f"Checkpoint due tomorrow: {item.title}",
            link="/student/plan",
        )
        item.reminder_sent_at = timezone.now()
        item.save(update_fields=["reminder_sent_at"])
        count += 1
    return count
