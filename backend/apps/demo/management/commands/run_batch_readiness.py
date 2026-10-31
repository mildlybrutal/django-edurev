import time

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import BackgroundJob, Institution, JobStatus
from apps.reporting.tasks import batch_readiness_task


class Command(BaseCommand):
    help = (
        "Queue the batch-readiness Celery job for an institution and wait for the worker to finish, printing "
        "the measured duration (P06 acceptance: 5,000 students in under 15 minutes)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--institution", default="loadtest")
        parser.add_argument("--timeout", type=int, default=1800, help="Seconds to wait for the worker.")

    def handle(self, *args, institution, timeout, **options):
        inst = Institution.objects.filter(code=institution).first()
        if inst is None:
            raise CommandError(f"No institution '{institution}'.")
        job = BackgroundJob.objects.create(institution=inst, kind="batch_readiness", params={"source": "command"})
        batch_readiness_task.delay(job.pk)  # runs on the Celery worker, not in this process
        self.stdout.write(f"Queued job {job.pk}; waiting for the worker…")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job.refresh_from_db()
            if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
                break
            time.sleep(2)
        if job.status != JobStatus.SUCCEEDED:
            raise CommandError(f"Job {job.pk} ended as {job.status}: {job.error}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Batch readiness for {job.result['students']} students: {job.duration_seconds:.1f}s on the worker "
                f"(average readiness {job.result['average_readiness']}%)."
            )
        )
