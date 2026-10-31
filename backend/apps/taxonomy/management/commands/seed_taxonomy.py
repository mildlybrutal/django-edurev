from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Institution
from apps.taxonomy.seeding import seed_taxonomy


class Command(BaseCommand):
    help = "Load the starter skill taxonomy (software development, data, testing roles) for an institution."

    def add_arguments(self, parser):
        parser.add_argument("institution_code")

    def handle(self, *args, institution_code, **options):
        institution = Institution.objects.filter(code=institution_code).first()
        if institution is None:
            raise CommandError(f"No institution with code '{institution_code}'.")
        counts = seed_taxonomy(institution)
        self.stdout.write(self.style.SUCCESS(f"Taxonomy ready for {institution.code}: {counts}"))
