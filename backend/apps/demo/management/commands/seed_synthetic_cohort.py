import time

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Institution
from apps.demo.seeding import synthetic_cohort


class Command(BaseCommand):
    help = "Bulk-create synthetic students with evidence for load testing (e.g. --students 5000)."

    def add_arguments(self, parser):
        parser.add_argument("--institution", default="loadtest")
        parser.add_argument("--students", type=int, default=5000)

    def handle(self, *args, institution, students, **options):
        if institution == "demo":
            raise CommandError("Use a separate institution for load tests so demo analytics stay readable.")
        inst, _ = Institution.objects.get_or_create(
            code=institution, defaults={"name": f"Load test ({institution}, synthetic data)"}
        )
        started = time.monotonic()
        made = synthetic_cohort(inst, students)
        self.stdout.write(self.style.SUCCESS(f"Created {made} synthetic students in {time.monotonic() - started:.1f}s"))
