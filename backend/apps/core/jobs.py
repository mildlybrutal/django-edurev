from django.utils import timezone

from .models import JobStatus


def execute_job(job, fn):
    """Run `fn` while recording status, timing, result and any error on a BackgroundJob."""
    job.status = JobStatus.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])
    try:
        job.result = fn()
        job.status = JobStatus.SUCCEEDED
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)[:2000]
        raise
    finally:
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "result", "error", "finished_at"])
    return job
