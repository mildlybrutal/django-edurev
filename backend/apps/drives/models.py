"""M7 Drive & Eligibility Management."""

from django.db import models

from apps.core.models import TenantModel
from apps.taxonomy.models import Level


class Company(TenantModel):
    name = models.CharField(max_length=200)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["institution", "name"], name="drives_company_unique")]

    def __str__(self):
        return self.name


class DriveStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published (registration open)"
    REGISTRATION_CLOSED = "registration_closed", "Registration closed"
    SHORTLISTING = "shortlisting", "Shortlisting"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


ACTIVE_STATUSES = (DriveStatus.PUBLISHED, DriveStatus.REGISTRATION_CLOSED, DriveStatus.SHORTLISTING)


class JDStatus(models.TextChoices):
    NONE = "none", "No JD"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready for review"
    APPLIED = "applied", "Applied"
    FAILED = "failed", "Failed"


class Drive(TenantModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="drives")
    role_title = models.CharField(max_length=200)
    target_role = models.ForeignKey(
        "taxonomy.TargetRole", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    location = models.CharField(max_length=150, blank=True)
    compensation = models.CharField(max_length=100, blank=True)
    job_description = models.TextField(blank=True)
    jd_status = models.CharField(max_length=20, choices=JDStatus.choices, default=JDStatus.NONE)
    jd_extraction = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, choices=DriveStatus.choices, default=DriveStatus.DRAFT, db_index=True)
    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_closes_at = models.DateTimeField(null=True, blank=True)
    drive_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="+")
    last_matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} — {self.role_title}"


class RequirementSource(models.TextChoices):
    JD = "jd", "Extracted from JD"
    ROLE_TEMPLATE = "role_template", "Role template"
    MANUAL = "manual", "Added manually"


class DriveRequirement(TenantModel):
    drive = models.ForeignKey(Drive, on_delete=models.CASCADE, related_name="requirements")
    skill = models.ForeignKey("taxonomy.Skill", on_delete=models.PROTECT, related_name="+")
    required_level = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.INTERMEDIATE)
    weight = models.PositiveSmallIntegerField(default=1)
    is_mandatory = models.BooleanField(default=False)
    source = models.CharField(max_length=20, choices=RequirementSource.choices, default=RequirementSource.MANUAL)

    class Meta:
        ordering = ["-is_mandatory", "-weight", "skill__name"]
        constraints = [models.UniqueConstraint(fields=["drive", "skill"], name="drives_requirement_unique")]

    def __str__(self):
        return f"{self.drive_id}: {self.skill_id}@{self.required_level}"


class RuleType(models.TextChoices):
    MIN_CGPA = "min_cgpa", "Minimum CGPA"
    MAX_ACTIVE_BACKLOGS = "max_active_backlogs", "Maximum active backlogs"
    DEPARTMENT_IN = "department_in", "Department is one of"
    GRADUATION_YEAR_IN = "graduation_year_in", "Graduation year is one of"


class EligibilityRule(TenantModel):
    """Hard criteria. `value` shape depends on type: number for MIN_CGPA / MAX_ACTIVE_BACKLOGS,
    list of department codes or years for the *_IN types."""

    drive = models.ForeignKey(Drive, on_delete=models.CASCADE, related_name="eligibility_rules")
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    value = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["drive", "rule_type"], name="drives_rule_unique")]

    def __str__(self):
        return f"{self.rule_type}={self.value}"


class EligibilityResult(TenantModel):
    """Latest eligibility evaluation of a student for a drive. Independent of readiness."""

    drive = models.ForeignKey(Drive, on_delete=models.CASCADE, related_name="eligibility_results")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="+")
    is_eligible = models.BooleanField()
    reasons = models.JSONField()
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["drive", "student"], name="drives_eligibility_unique")]
        indexes = [models.Index(fields=["drive", "is_eligible"])]


class RegistrationStatus(models.TextChoices):
    REGISTERED = "registered", "Registered"
    WITHDRAWN = "withdrawn", "Withdrawn"
    SHORTLISTED = "shortlisted", "Shortlisted"
    NOT_SHORTLISTED = "not_shortlisted", "Not shortlisted"
    SELECTED = "selected", "Selected"
    NOT_SELECTED = "not_selected", "Not selected"


ACTIVE_REGISTRATION = (
    RegistrationStatus.REGISTERED,
    RegistrationStatus.SHORTLISTED,
    RegistrationStatus.NOT_SHORTLISTED,
    RegistrationStatus.SELECTED,
    RegistrationStatus.NOT_SELECTED,
)


class Registration(TenantModel):
    drive = models.ForeignKey(Drive, on_delete=models.CASCADE, related_name="registrations")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="registrations")
    status = models.CharField(max_length=20, choices=RegistrationStatus.choices, default=RegistrationStatus.REGISTERED)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registered_at"]
        constraints = [models.UniqueConstraint(fields=["drive", "student"], name="drives_registration_unique")]
        indexes = [models.Index(fields=["drive", "status"])]

    def __str__(self):
        return f"{self.drive_id}:{self.student_id} {self.status}"
