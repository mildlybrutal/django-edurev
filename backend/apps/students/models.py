"""Student academic record. Academic fields are maintained by the placement cell (or an
ERP/SIS import), never edited by the student."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TenantModel

from .validators import validate_registration_number


class Department(TenantModel):
    code = models.CharField(max_length=20, help_text="Short code used in eligibility rules, e.g. CSE.")
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="students_department_code_unique")]

    def __str__(self):
        return self.code


class StudentProfile(TenantModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    roll_number = models.CharField(
        "registration number",
        max_length=40,
        validators=[validate_registration_number],
        help_text="University registration number: exactly 8 digits.",
    )
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="students")
    graduation_year = models.PositiveSmallIntegerField()
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(10)])
    active_backlogs = models.PositiveSmallIntegerField(default=0)
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mentees",
        help_text="Faculty member who verifies this student's evidence.",
    )
    academic_record_verified = models.BooleanField(
        default=True,
        help_text="False when the student entered CGPA/backlogs at sign-up and the placement cell has not "
        "confirmed them.",
    )
    # Student-editable fields.
    headline = models.CharField(max_length=160, blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["roll_number"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "roll_number"], name="students_roll_number_unique")
        ]
        indexes = [models.Index(fields=["institution", "graduation_year"])]

    def __str__(self):
        return self.roll_number

    @property
    def name(self):
        return self.user.get_full_name() or self.user.email


def _resume_storage():
    from django.core.files.storage import storages

    return storages["resumes"]


class StudentResume(TenantModel):
    """Uploaded resume (PDF). The newest upload is current; older ones are kept as history."""

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="resumes")
    file = models.FileField(storage=_resume_storage, max_length=300)
    original_name = models.CharField(max_length=200)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    is_current = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"], condition=models.Q(is_current=True), name="students_one_current_resume"
            )
        ]

    def __str__(self):
        return self.original_name
