from celery import shared_task

from .models import CodingProfile


@shared_task
def sync_coding_profile(profile_id):
    from .services import sync

    profile = CodingProfile.objects.select_related("student__institution").filter(pk=profile_id).first()
    if profile is not None:
        sync(profile)


@shared_task
def refresh_stale_profiles(limit=40):
    """Daily (Celery Beat): re-sync profiles older than a day, a bounded batch per run to respect
    GitHub's unauthenticated rate limit."""
    from .services import due_for_refresh

    ids = list(due_for_refresh().order_by("last_synced_at").values_list("pk", flat=True)[:limit])
    for pk in ids:
        sync_coding_profile.delay(pk)
    return len(ids)
