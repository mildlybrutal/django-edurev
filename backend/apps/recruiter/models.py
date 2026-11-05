"""M10 Recruiter portal: time-boxed, drive-scoped, field-limited access with full logging."""

from django.db import models
from django.utils import timezone

from apps.core.models import AppendOnlyModel, Institution, TenantModel

# The complete list of student fields that can ever be released to a recruiter. A grant picks
# a subset; anything not listed here can never be serialized to a recruiter (docs/data-release-policy.md).
RELEASABLE_FIELDS = {
    "name": "Full name",
    "email": "Institutional email",
    "department": "Department",
    "graduation_year": "Graduation year",
    "cgpa": "CGPA",
    "compatibility": "Skill match % for this drive",
    "readiness": "Readiness % and dimensions for this drive",
    "skills": "Skill profile (levels and verification status)",
    "evidence": "Evidence titles, types and verification status (no files or links)",
    "registration_status": "Registration / shortlist status",
    "coding_activity": "Coding-activity rating (GitHub / LeetCode, unverified)",
    "resume": "Resume (PDF, short-lived view link; each view is logged)",
}
DEFAULT_FIELDS = ["name", "department", "graduation_year", "compatibility", "skills", "registration_status"]


class CandidateScope(models.TextChoices):
    REGISTERED = "registered", "All registered students"
    SHORTLISTED = "shortlisted", "Shortlisted students only"


class GrantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"


class RecruiterAccessGrant(TenantModel):
    recruiter = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="recruiter_grants")
    drive = models.ForeignKey("drives.Drive", on_delete=models.CASCADE, related_name="recruiter_grants")
    allowed_fields = models.JSONField(default=list)
    candidate_scope = models.CharField(max_length=20, choices=CandidateScope.choices, default=CandidateScope.REGISTERED)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=GrantStatus.choices, default=GrantStatus.ACTIVE)
    granted_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recruiter", "drive", "status"])]

    def __str__(self):
        return f"{self.recruiter_id} -> drive {self.drive_id}"

    def is_valid(self, now=None):
        now = now or timezone.now()
        return self.status == GrantStatus.ACTIVE and self.starts_at <= now < self.expires_at


class AccessAction(models.TextChoices):
    LIST = "list", "Listed candidates"
    SEARCH = "search", "Searched candidates"
    DETAIL = "detail", "Viewed candidate"
    RESUME = "resume", "Opened resume"
    BROADCAST = "broadcast", "Sent broadcast"
    DENIED = "denied", "Access denied"


class AccessLog(AppendOnlyModel):
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="+")
    recruiter = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    grant = models.ForeignKey(RecruiterAccessGrant, null=True, on_delete=models.PROTECT, related_name="logs")
    drive_id_requested = models.PositiveBigIntegerField(null=True)
    action = models.CharField(max_length=10, choices=AccessAction.choices)
    path = models.CharField(max_length=300)
    query = models.JSONField(default=dict, blank=True)
    student_ids = models.JSONField(default=list, blank=True)
    fields_released = models.JSONField(default=list, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.recruiter_id} {self.action} {self.path}"


class BroadcastAudience(models.TextChoices):
    ALL = "all", "All candidates in my access"
    SHORTLISTED = "shortlisted", "Shortlisted candidates only"


class RecruiterBroadcast(TenantModel):
    """A message a recruiter sends to the candidates of a drive they hold a valid grant for. The
    recipients are resolved from the grant's scoped candidate set (never a recruiter-supplied
    list) and delivered as in-app notifications; the recruiter only ever sees the count."""

    grant = models.ForeignKey(RecruiterAccessGrant, on_delete=models.PROTECT, related_name="broadcasts")
    recruiter = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    drive = models.ForeignKey("drives.Drive", on_delete=models.CASCADE, related_name="recruiter_broadcasts")
    audience = models.CharField(max_length=20, choices=BroadcastAudience.choices, default=BroadcastAudience.ALL)
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=2000)
    recipient_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["drive", "recruiter", "created_at"])]

    def __str__(self):
        return f"{self.recruiter_id} -> drive {self.drive_id}: {self.title}"
