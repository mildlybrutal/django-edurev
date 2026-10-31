from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from apps.accounts.roles import Role, has_role

from .models import StudentProfile
from .validators import REGISTRATION_NUMBER_MESSAGE, validate_registration_number


class StudentError(ValueError):
    pass


def _check_registration_number(value):
    from django.core.exceptions import ValidationError

    try:
        validate_registration_number(value)
    except ValidationError as exc:
        raise StudentError(REGISTRATION_NUMBER_MESSAGE) from exc


@transaction.atomic
def create_student(
    *,
    institution,
    email,
    first_name,
    last_name,
    roll_number,
    department,
    graduation_year,
    cgpa,
    active_backlogs=0,
    mentor=None,
    password=None,
):
    """Create a student account and academic record (placement cell / ERP import)."""
    _check_registration_number(roll_number)
    if department.institution_id != institution.id:
        raise StudentError("Department belongs to another institution.")
    if mentor is not None and (mentor.institution_id != institution.id or not has_role(mentor, Role.FACULTY)):
        raise StudentError("Mentor must be a faculty member of the same institution.")
    User = get_user_model()
    if User.objects.filter(email__iexact=email).exists():
        raise StudentError("An account with this email already exists.")
    user = User.objects.create_user(
        email=email, password=password, first_name=first_name, last_name=last_name, institution=institution
    )
    if password is None:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    user.groups.add(Group.objects.get(name=Role.STUDENT))
    return StudentProfile.objects.create(
        institution=institution,
        user=user,
        roll_number=roll_number,
        department=department,
        graduation_year=graduation_year,
        cgpa=cgpa,
        active_backlogs=active_backlogs,
        mentor=mentor,
    )


ACADEMIC_FIELDS = (
    "roll_number",
    "department",
    "graduation_year",
    "cgpa",
    "active_backlogs",
    "mentor",
    "academic_record_verified",
)
STUDENT_EDITABLE_FIELDS = ("headline", "github_url", "linkedin_url")


def update_student(student, *, by_staff, **changes):
    allowed = ACADEMIC_FIELDS + STUDENT_EDITABLE_FIELDS if by_staff else STUDENT_EDITABLE_FIELDS
    unknown = set(changes) - set(allowed)
    if unknown:
        raise StudentError(f"Not allowed to change: {', '.join(sorted(unknown))}.")
    if "roll_number" in changes:
        _check_registration_number(changes["roll_number"])
    mentor = changes.get("mentor")
    if mentor is not None and (mentor.institution_id != student.institution_id or not has_role(mentor, Role.FACULTY)):
        raise StudentError("Mentor must be a faculty member of the same institution.")
    for field, value in changes.items():
        setattr(student, field, value)
    student.save()
    return student


@transaction.atomic
def self_signup(
    *,
    institution,
    email,
    password,
    first_name,
    last_name,
    roll_number,
    department,
    graduation_year,
    cgpa,
    active_backlogs,
):
    """A student creates their own account. Academic values are self-declared until the placement
    cell confirms them (academic_record_verified=False), and the password must pass Django's validators."""
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    if not institution.is_active or not institution.allow_student_signup:
        raise StudentError("This institution does not accept self sign-up.")
    domain = institution.student_email_domain.strip().lower().lstrip("@")
    if domain and not email.lower().endswith("@" + domain):
        raise StudentError(f"Use your institutional email address (@{domain}).")
    _check_registration_number(roll_number)
    if StudentProfile.objects.filter(institution=institution, roll_number__iexact=roll_number).exists():
        raise StudentError("A student with this registration number is already registered. Contact the placement cell.")
    probe = get_user_model()(email=email, first_name=first_name, last_name=last_name)
    try:
        validate_password(password, user=probe)
    except ValidationError as exc:
        raise StudentError(" ".join(exc.messages)) from exc
    student = create_student(
        institution=institution,
        email=email,
        first_name=first_name,
        last_name=last_name,
        roll_number=roll_number,
        department=department,
        graduation_year=graduation_year,
        cgpa=cgpa,
        active_backlogs=active_backlogs,
        password=password,
    )
    student.academic_record_verified = False
    student.save(update_fields=["academic_record_verified", "updated_at"])
    return student


def complete_onboarding(student):
    from django.utils import timezone

    if student.onboarding_completed_at is None:
        student.onboarding_completed_at = timezone.now()
        student.save(update_fields=["onboarding_completed_at", "updated_at"])
    return student


KEEP_RESUME_VERSIONS = 3


@transaction.atomic
def upload_resume(student, uploaded, *, uploaded_by):
    from apps.core.services import record_audit

    from . import resumes
    from .models import StudentResume

    digest = resumes.validate_pdf(uploaded)
    resumes.ensure_bucket()
    name = resumes.resume_storage().save(resumes.object_key(student, uploaded.name), uploaded)
    StudentResume.objects.filter(student=student, is_current=True).update(is_current=False)
    resume = StudentResume.objects.create(
        institution_id=student.institution_id,
        student=student,
        file=name,
        original_name=uploaded.name[-200:],
        size=uploaded.size,
        sha256=digest,
        uploaded_by=uploaded_by,
    )
    for old in StudentResume.objects.filter(student=student, is_current=False).order_by("-created_at")[
        KEEP_RESUME_VERSIONS - 1 :
    ]:
        old.file.delete(save=False)
        old.delete()
    record_audit(actor=uploaded_by, action="student.resume.upload", target=resume, after={"size": uploaded.size})
    return resume


def delete_resume(student, *, actor):
    from apps.core.services import record_audit

    from .models import StudentResume

    removed = 0
    for resume in StudentResume.objects.filter(student=student):
        resume.file.delete(save=False)
        resume.delete()
        removed += 1
    if removed:
        record_audit(actor=actor, action="student.resume.delete", target=student)
    return removed


def current_resume(student):
    from .models import StudentResume

    return StudentResume.objects.filter(student=student, is_current=True).first()
