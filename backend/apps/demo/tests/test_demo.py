import pytest

from apps.core.models import Institution
from apps.demo.seeding import seed_demo, synthetic_cohort
from apps.drives.models import Drive, DriveStatus, JDStatus
from apps.matching.models import MatchResult
from apps.planning.models import PreparationPlan
from apps.recruiter.models import RecruiterAccessGrant
from apps.students.models import StudentProfile

pytestmark = pytest.mark.django_db


def test_seed_demo_builds_the_whole_story_and_is_idempotent():
    result = seed_demo(password="Demo-Pass-2026", students=8)
    institution = Institution.objects.get(code="demo")
    assert result["students"] == 8
    assert StudentProfile.objects.filter(institution=institution).count() == 8
    backend = Drive.objects.get(institution=institution, role_title="Backend Engineer")
    assert backend.jd_status == JDStatus.APPLIED and backend.requirements.count() >= 5
    assert backend.eligibility_rules.count() == 4
    assert MatchResult.objects.filter(drive=backend).count() == 8
    assert Drive.objects.filter(institution=institution, status=DriveStatus.DRAFT).count() == 1
    assert PreparationPlan.objects.filter(student__user__email="student@demo.example.test").exists()
    assert RecruiterAccessGrant.objects.filter(drive=backend).exists()
    again = seed_demo(password="ignored", students=8)
    assert again["created_accounts"] == []
    assert StudentProfile.objects.filter(institution=institution).count() == 8


def test_synthetic_cohort_bulk_creates_students():
    institution = Institution.objects.create(name="Load", code="loadtest")
    assert synthetic_cohort(institution, 25, chunk=10) == 25
    assert StudentProfile.objects.filter(institution=institution).count() == 25
    assert synthetic_cohort(institution, 5) == 5  # appends, never collides
