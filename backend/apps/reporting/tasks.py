from celery import shared_task

from apps.core.models import BackgroundJob


@shared_task
def batch_readiness_task(job_id):
    from apps.core.jobs import execute_job

    from .services import run_batch_readiness

    job = BackgroundJob.objects.get(pk=job_id)
    execute_job(job, lambda: run_batch_readiness(job.institution_id, job=job))
    return job.pk
