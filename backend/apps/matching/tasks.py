from celery import shared_task

from apps.core.models import BackgroundJob
from apps.drives.models import Drive


@shared_task
def run_drive_matching_task(drive_id, job_id=None, notify_students=False):
    from apps.core.jobs import execute_job

    from .services import run_drive_matching

    drive = Drive.objects.filter(pk=drive_id).first()
    if drive is None:
        return None
    job = BackgroundJob.objects.filter(pk=job_id).first() if job_id else None
    if job is None:
        job = BackgroundJob.objects.create(
            institution_id=drive.institution_id, kind="drive_matching", params={"drive_id": drive_id}
        )
    execute_job(job, lambda: run_drive_matching(drive, job=job, notify_students=notify_students))
    return job.pk
