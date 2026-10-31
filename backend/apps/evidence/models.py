"""M2 Evidence Ingestion. Every item records where it came from (source type, URL/reference)
and its verification status. External coding activity is evidence, not proof (AGENTS.md §3)."""

from django.db import models

from apps.core.models import TenantModel
from apps.taxonomy.models import Level


class SourceType(models.TextChoices):
    ACADEMIC = "academic", "Academic record"
    PROJECT = "project", "Project"
    CERTIFICATION = "certification", "Certification"
    ASSESSMENT = "assessment", "Assessment"
    MOCK_INTERVIEW = "mock_interview", "Mock interview"
    GITHUB = "github", "GitHub"
    LEETCODE = "leetcode", "LeetCode"
    CODECHEF = "codechef", "CodeChef"
    CODEFORCES = "codeforces", "Codeforces"
    OTHER = "other", "Other"


# Recorded by staff from institutional systems; verified on creation and never student-editable.
INSTITUTIONAL_SOURCES = {SourceType.ACADEMIC, SourceType.ASSESSMENT, SourceType.MOCK_INTERVIEW}
EXTERNAL_PLATFORM_SOURCES = {SourceType.GITHUB, SourceType.LEETCODE, SourceType.CODECHEF, SourceType.CODEFORCES}


class VerificationStatus(models.TextChoices):
    SELF_REPORTED = "self_reported", "Self-reported"
    PENDING = "pending", "Pending verification"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class EvidenceItem(TenantModel):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="evidence")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    source_url = models.URLField(blank=True)
    external_reference = models.CharField(max_length=200, blank=True, help_text="Handle, certificate ID, etc.")
    extracted_data = models.JSONField(default=dict, blank=True, help_text="Structured facts, e.g. problem counts.")
    submitted_at = models.DateTimeField(auto_now_add=True)
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.SELF_REPORTED, db_index=True
    )
    recorded_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [models.Index(fields=["student", "verification_status"])]

    def __str__(self):
        return self.title

    @property
    def is_verified(self):
        return self.verification_status == VerificationStatus.VERIFIED


class EvidenceSkillTag(TenantModel):
    evidence = models.ForeignKey(EvidenceItem, on_delete=models.CASCADE, related_name="skill_tags")
    skill = models.ForeignKey("taxonomy.Skill", on_delete=models.PROTECT, related_name="+")
    claimed_level = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.BEGINNER)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["evidence", "skill"], name="evidence_tag_unique")]

    def __str__(self):
        return f"{self.evidence_id}: {self.skill_id}@{self.claimed_level}"
