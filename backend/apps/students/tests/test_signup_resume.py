from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from apps.accounts.roles import Role
from apps.core.models import AuditLog
from apps.students.models import StudentProfile, StudentResume

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def open_institution(institution, departments):
    institution.allow_student_signup = True
    institution.save()
    return institution


def signup_payload(**overrides):
    return {
        "institution_code": "synthetic-u",
        "email": "new.student@example.test",
        "password": "Sturdy-Pass-2026",
        "first_name": "New",
        "last_name": "Student",
        "roll_number": "12301001",
        "department_id": None,
        "graduation_year": 2027,
        "cgpa": "8.10",
        "active_backlogs": 0,
        **overrides,
    }


def test_signup_options_lists_only_open_institutions(open_institution, csrf_client):
    from apps.core.models import Institution

    Institution.objects.create(name="Closed", code="closed")
    body = csrf_client.get("/api/v1/auth/signup-options/").json()
    assert [i["code"] for i in body] == ["synthetic-u"]
    assert {d["code"] for d in body[0]["departments"]} == {"CSE", "IT", "ECE"}


def test_student_signs_up_and_is_signed_in(open_institution, departments, csrf_client):
    response = csrf_client.post(
        "/api/v1/auth/signup/", signup_payload(department_id=departments["CSE"].pk), format="json"
    )
    assert response.status_code == 201, response.content
    assert response.json()["roles"] == ["student"]
    assert csrf_client.get("/api/v1/auth/me/").status_code == 200
    student = StudentProfile.objects.get(roll_number="12301001")
    assert student.academic_record_verified is False  # self-declared until the placement cell confirms
    assert student.onboarding_completed_at is None
    assert AuditLog.objects.filter(action="auth.signup").exists()


def test_signup_refused_when_institution_closed(institution, departments, csrf_client):
    response = csrf_client.post(
        "/api/v1/auth/signup/", signup_payload(department_id=departments["CSE"].pk), format="json"
    )
    assert response.status_code == 400


def test_signup_enforces_email_domain_password_strength_and_unique_roll(
    open_institution, departments, csrf_client, make_student
):
    open_institution.student_email_domain = "univ.edu"
    open_institution.save()
    dept = departments["CSE"].pk
    assert (
        "univ.edu"
        in csrf_client.post("/api/v1/auth/signup/", signup_payload(department_id=dept), format="json").json()["detail"]
    )
    weak = signup_payload(department_id=dept, email="a@univ.edu", password="password")
    assert csrf_client.post("/api/v1/auth/signup/", weak, format="json").status_code == 400
    make_student(email="x@univ.edu")  # registration number 12300001
    dup = signup_payload(department_id=dept, email="b@univ.edu", roll_number="12300001")
    assert "registration number" in csrf_client.post("/api/v1/auth/signup/", dup, format="json").json()["detail"]


def test_signup_requires_csrf(open_institution, departments):
    from rest_framework.test import APIClient

    response = APIClient(enforce_csrf_checks=True).post(
        "/api/v1/auth/signup/", signup_payload(department_id=departments["CSE"].pk), format="json"
    )
    assert response.status_code == 403


def test_onboarding_flow(make_student, as_user):
    student = make_student()
    client = as_user(student.user)
    assert client.get("/api/v1/students/me/onboarding/").json()["required"] is True
    assert client.post("/api/v1/students/me/onboarding/").json() == {"required": False}
    assert client.get("/api/v1/students/me/onboarding/").json()["required"] is False


def test_officer_confirms_self_declared_academics(make_student, officer, as_user):
    student = make_student()
    student.academic_record_verified = False
    student.save()
    response = as_user(officer).patch(
        f"/api/v1/students/{student.pk}/", {"academic_record_verified": True}, format="json"
    )
    assert response.json()["academic_record_verified"] is True
    response = as_user(student.user).patch("/api/v1/students/me/", {"academic_record_verified": False}, format="json")
    student.refresh_from_db()
    assert student.academic_record_verified is True  # students can't change it


# --- resumes ---------------------------------------------------------------------------------


def upload(client, content=PDF, name="resume.pdf"):
    return client.post(
        "/api/v1/students/me/resume/",
        {"file": SimpleUploadedFile(name, content, "application/pdf")},
        format="multipart",
    )


def test_student_uploads_and_views_resume(make_student, as_user):
    client = as_user(make_student().user)
    response = upload(client)
    assert response.status_code == 201, response.content
    body = client.get("/api/v1/students/me/resume/").json()
    assert body["name"] == "resume.pdf" and body["url"] and body["expires_in"] == 300


def test_resume_validation(make_student, as_user):
    client = as_user(make_student().user)
    assert upload(client, content=b"MZ\x90\x00 not a pdf", name="cv.pdf").status_code == 400
    assert upload(client, name="cv.docx").status_code == 400
    with override_settings(RESUME_MAX_BYTES=10):
        assert upload(client).status_code == 400


def test_new_upload_replaces_current_and_keeps_bounded_history(make_student, as_user):
    student = make_student()
    client = as_user(student.user)
    for _ in range(5):
        upload(client)
    assert StudentResume.objects.filter(student=student, is_current=True).count() == 1
    assert StudentResume.objects.filter(student=student).count() == 3


def test_resume_visible_to_mentor_and_cell_not_other_students(make_student, faculty, officer, make_user, as_user):
    owner, other = make_student(), make_student()
    upload(as_user(owner.user))
    assert as_user(faculty).get(f"/api/v1/students/{owner.pk}/resume/").status_code == 200
    assert as_user(officer).get(f"/api/v1/students/{owner.pk}/resume/").status_code == 200
    assert as_user(other.user).get(f"/api/v1/students/{owner.pk}/resume/").status_code == 404
    stranger = make_user(email="f2@example.test", roles=[Role.FACULTY])
    assert as_user(stranger).get(f"/api/v1/students/{owner.pk}/resume/").status_code == 404
    assert AuditLog.objects.filter(action="student.resume.view").count() == 2
    # Staff can view but never upload or delete someone's resume.
    assert as_user(officer).delete(f"/api/v1/students/{owner.pk}/resume/").status_code == 403


def test_resume_and_coding_count_toward_profile_completion(make_student, as_user):
    student = make_student()
    client = as_user(student.user)
    checks = {c["key"]: c["done"] for c in client.get("/api/v1/students/me/profile/").json()["completion"]["checks"]}
    assert checks["resume"] is False
    upload(client)
    checks = {c["key"]: c["done"] for c in client.get("/api/v1/students/me/profile/").json()["completion"]["checks"]}
    assert checks["resume"] is True


def test_recruiter_resume_link_only_when_released_and_logged(
    make_student, make_drive, make_user, head, as_user, taxonomy
):
    from rest_framework.test import APIClient

    from apps.accounts.services import issue_tokens
    from apps.drives import services as drive_services
    from apps.recruiter import services as recruiter_services
    from apps.recruiter.models import AccessLog

    student = make_student()
    upload(as_user(student.user))
    drive = make_drive(requirements=[(taxonomy("Django"), 2, 1, True)])
    drive_services.register(drive, student)
    recruiter = make_user(email="rec@example.test", roles=[Role.RECRUITER])
    grant = recruiter_services.create_grant(
        recruiter=recruiter,
        drive=drive,
        allowed_fields=["name"],
        expires_at=timezone.now() + timedelta(days=1),
        granted_by=head,
    )
    client = APIClient()
    client.cookies["rc_access"] = issue_tokens(recruiter, "recruiter").access
    url = f"/api/v1/recruiter/drives/{drive.pk}/candidates/{student.pk}/resume/"
    assert client.get(url).status_code == 404  # resume not released
    recruiter_services.update_grant(grant, actor=head, allowed_fields=["name", "resume", "coding_activity"])
    detail = client.get(f"/api/v1/recruiter/drives/{drive.pk}/candidates/{student.pk}/").json()
    assert detail["resume_available"] is True and "coding_activity" in detail
    assert client.get(url).status_code == 200
    assert AccessLog.objects.filter(recruiter=recruiter, action="resume").count() == 1


def test_signup_rejects_non_eight_digit_registration_number(open_institution, departments, csrf_client):
    payload = signup_payload(department_id=departments["CSE"].pk, roll_number="E2E12345")
    response = csrf_client.post("/api/v1/auth/signup/", payload, format="json")
    assert response.status_code == 400
    assert not StudentProfile.objects.filter(roll_number="E2E12345").exists()
