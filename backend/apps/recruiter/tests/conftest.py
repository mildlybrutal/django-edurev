"""Shared recruiter-portal fixtures."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.roles import Role
from apps.drives import services as drive_services
from apps.evidence.models import SourceType
from apps.matching.services import run_drive_matching
from apps.recruiter import services
from apps.taxonomy.models import Level


@pytest.fixture
def world(make_user, make_student, make_drive, taxonomy, give_evidence, head):
    """Drive A and Drive B with disjoint registrations; recruiter A granted on Drive A only."""
    django = taxonomy("Django")
    drive_a = make_drive(role="Backend Engineer", company="Alpha", requirements=[(django, Level.INTERMEDIATE, 1, True)])
    drive_b = make_drive(
        role="Data Analyst", company="Beta", requirements=[(taxonomy("SQL"), Level.INTERMEDIATE, 1, True)]
    )
    in_a = make_student(name="InA")
    in_b = make_student(name="InB")
    unregistered = make_student(name="Nowhere")
    for s in (in_a, in_b, unregistered):
        give_evidence(s, SourceType.PROJECT, f"{s.name} project", [(django, Level.INTERMEDIATE)], verified=True)
    drive_services.register(drive_a, in_a)
    drive_services.register(drive_b, in_b)
    run_drive_matching(drive_a)
    run_drive_matching(drive_b)
    recruiter_a = make_user(email="rec-a@alpha.example", roles=[Role.RECRUITER])
    recruiter_b = make_user(email="rec-b@beta.example", roles=[Role.RECRUITER])
    grant_a = services.create_grant(
        recruiter=recruiter_a,
        drive=drive_a,
        allowed_fields=["name", "skills"],
        expires_at=timezone.now() + timedelta(days=7),
        granted_by=head,
    )
    return {
        "drive_a": drive_a,
        "drive_b": drive_b,
        "in_a": in_a,
        "in_b": in_b,
        "unregistered": unregistered,
        "recruiter_a": recruiter_a,
        "recruiter_b": recruiter_b,
        "grant_a": grant_a,
    }
