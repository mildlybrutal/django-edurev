from celery import shared_task
from django.core.cache import cache

from apps.students.models import StudentProfile


@shared_task
def recompute_student(student_id):
    """Rebuild one student's skill claims, then their general readiness snapshot."""
    from apps.readiness.services import compute_general_snapshot

    from .services import recompute_profile

    cache.delete(f"profile-recompute:{student_id}")
    student = StudentProfile.objects.filter(pk=student_id).first()
    if student is None:
        return None
    recompute_profile(student)
    snapshot = compute_general_snapshot(student)
    refresh_active_matches(student)
    return snapshot.pk


def refresh_active_matches(student):
    """Keep stored drive results (eligibility, compatibility, drive readiness, gaps) in step with
    the rebuilt profile, so officers and recruiters never see a stale skill match."""
    from apps.drives.models import ACTIVE_STATUSES, Drive
    from apps.matching.services import match_student

    for drive in Drive.objects.filter(institution_id=student.institution_id, status__in=ACTIVE_STATUSES):
        match_student(drive, student)
