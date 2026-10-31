from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.roles import Role
from apps.accounts.services import issue_tokens
from apps.core.models import Institution


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def institution(db):
    return Institution.objects.create(name="Synthetic University", code="synthetic-u")


@pytest.fixture
def make_user(db, institution, django_user_model):
    def _make(email="user@example.test", password="Correct-Horse-9", roles=(), **extra):
        extra.setdefault("institution", institution)
        user = django_user_model.objects.create_user(email=email, password=password, **extra)
        for role in roles:
            user.groups.add(Group.objects.get(name=role))
        return user

    return _make


@pytest.fixture
def csrf_client():
    """API client that enforces CSRF like a browser would and carries the CSRF cookie + header."""

    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/v1/auth/csrf/")
    client.credentials(HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
    return client


@pytest.fixture
def login(csrf_client):
    def _login(email, password="Correct-Horse-9"):
        response = csrf_client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")
        assert response.status_code == 200, response.content
        return csrf_client

    return _login


@pytest.fixture
def as_user():
    """Client authenticated as `user` via a real portal-bound access cookie (CSRF not enforced)."""

    def _client(user, portal="internal"):
        client = APIClient()
        cookie = "rc_access" if portal == "recruiter" else "pa_access"
        client.cookies[cookie] = issue_tokens(user, portal).access
        return client

    return _client


@pytest.fixture
def student(make_user):
    return make_user(email="student@example.test", roles=[Role.STUDENT])


# --- domain fixtures -----------------------------------------------------------------------------


@pytest.fixture
def taxonomy(institution):
    """Seeded starter taxonomy; returns a lookup by name or synonym."""
    from apps.taxonomy.seeding import seed_taxonomy
    from apps.taxonomy.selectors import resolve_skill

    seed_taxonomy(institution)

    def skill(name):
        found = resolve_skill(institution, name)
        assert found is not None, name
        return found

    return skill


@pytest.fixture
def departments(institution):
    from apps.students.models import Department

    return {
        code: Department.objects.create(institution=institution, code=code, name=name)
        for code, name in [("CSE", "Computer Science"), ("IT", "Information Technology"), ("ECE", "Electronics")]
    }


@pytest.fixture
def faculty(make_user):
    return make_user(email="faculty@example.test", roles=[Role.FACULTY], first_name="Fac", last_name="Ulty")


@pytest.fixture
def officer(make_user):
    return make_user(email="officer@example.test", roles=[Role.PLACEMENT_OFFICER])


@pytest.fixture
def head(make_user):
    return make_user(email="head@example.test", roles=[Role.PLACEMENT_HEAD])


@pytest.fixture
def admin_user(make_user):
    return make_user(email="admin@example.test", roles=[Role.ADMIN])


@pytest.fixture
def make_student(institution, departments, faculty):
    from apps.students.services import create_student

    counter = {"n": 0}

    def _make(name="Student", dept="CSE", cgpa="8.00", backlogs=0, year=2027, mentor=..., email=None):
        counter["n"] += 1
        n = counter["n"]
        return create_student(
            institution=institution,
            email=email or f"s{n}@example.test",
            first_name=name,
            last_name=str(n),
            roll_number=f"1230{n:04d}",
            department=departments[dept],
            graduation_year=year,
            cgpa=Decimal(cgpa),
            active_backlogs=backlogs,
            mentor=faculty if mentor is ... else mentor,
            password="Correct-Horse-9",
        )

    return _make


@pytest.fixture
def give_evidence():
    """Attach evidence directly through services and rebuild the student's profile."""
    from apps.evidence import services as ev
    from apps.evidence.models import INSTITUTIONAL_SOURCES, VerificationStatus
    from apps.profiles.services import recompute_profile

    def _give(student, source, title, tags, *, verified=False, recorder=None):
        if source in INSTITUTIONAL_SOURCES:
            item = ev.record_institutional_evidence(
                student=student, source_type=source, title=title, recorded_by=recorder or student.user, tags=tags
            )
        else:
            item = ev.submit_evidence(student=student, source_type=source, title=title, tags=tags)
            if verified:
                ev.set_status(item, VerificationStatus.VERIFIED)
        recompute_profile(student)
        return item

    return _give


@pytest.fixture
def make_drive(institution, officer):
    from apps.drives import services as ds
    from apps.drives.models import Company, DriveStatus

    def _make(
        role="Backend Engineer", company="Synthetic Corp", requirements=(), rules=(), publish=True, drive_date=None
    ):
        comp, _ = Company.objects.get_or_create(institution=institution, name=company)
        drive = ds.create_drive(
            institution=institution,
            company=comp,
            role_title=role,
            created_by=officer,
            registration_opens_at=timezone.now() - timedelta(days=1),
            registration_closes_at=timezone.now() + timedelta(days=7),
            drive_date=drive_date or (timezone.localdate() + timedelta(days=30)),
        )
        for skill, level, weight, mandatory in requirements:
            ds.set_requirement(drive, skill=skill, required_level=level, weight=weight, is_mandatory=mandatory)
        for rule_type, value in rules:
            ds.set_eligibility_rule(drive, rule_type, value)
        if publish:
            drive.status = DriveStatus.PUBLISHED
            drive.save(update_fields=["status"])
        return drive

    return _make
