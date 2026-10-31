from celery import shared_task

from .models import Drive


@shared_task
def process_jd_task(drive_id):
    from .services import run_jd_processing

    drive = Drive.objects.filter(pk=drive_id).first()
    if drive is not None:
        run_jd_processing(drive)
