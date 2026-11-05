import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.demo.seeding import grow_demo_cohort, seed_demo


class Command(BaseCommand):
    help = (
        "Create the synthetic demo: institution, one account per role, a mentored student cohort with evidence "
        "and assessments, four drives at different stages, matching, a plan and a recruiter grant. Idempotent. "
        "Never run against a database holding real student data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Password for every demo account (default: random, printed once).")
        parser.add_argument("--students", type=int, default=40, help="Size of the synthetic cohort (default 40).")
        parser.add_argument(
            "--add-students",
            type=int,
            metavar="N",
            help="Add N synthetic students to an existing demo, then re-run matching and batch readiness.",
        )

    def handle(self, *args, password=None, students=40, add_students=None, **options):
        if add_students is not None:
            if add_students < 1:
                raise CommandError("--add-students must be at least 1.")
            try:
                result = grow_demo_cohort(count=add_students)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(self.style.SUCCESS(f"Demo cohort grown: {result}"))
            return
        password = password or secrets.token_urlsafe(12)
        result = seed_demo(password=password, students=students)
        self.stdout.write(self.style.SUCCESS(f"Demo ready: {result}"))
        if result["created_accounts"]:
            self.stdout.write("Accounts created (all @demo.example.test, password shown once):")
            for email in result["created_accounts"]:
                self.stdout.write(f"  {email}")
            self.stdout.write(f"  password: {password}")
        else:
            self.stdout.write("Accounts already existed; passwords unchanged.")
