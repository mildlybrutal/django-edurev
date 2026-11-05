"""M6 Readiness Engine. The P06 specification names the dimensions (technical mastery, aptitude,
communication, project depth) but no formula; the formula here is a documented, versioned
implementation choice (docs/scoring-policy.md)."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import AppendOnlyModel, Institution, TenantModel

DIMENSIONS = ("technical", "aptitude", "communication", "project_depth", "coding_activity")


class ScoringConfig(TenantModel):
    """One row per version. Exactly one active version per institution; snapshots record which
    version produced them, so old results stay explainable after the policy changes."""

    version = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    weight_technical = models.PositiveSmallIntegerField(default=40)
    weight_aptitude = models.PositiveSmallIntegerField(default=20)
    weight_communication = models.PositiveSmallIntegerField(default=20)
    weight_project_depth = models.PositiveSmallIntegerField(default=20)
    weight_coding = models.PositiveSmallIntegerField(
        default=10, help_text="Coding activity (GitHub/LeetCode/Codeforces ratings): unverified external evidence."
    )
    unverified_multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.50"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="Credit given to the part of a skill level supported only by unverified evidence.",
    )
    technical_top_n = models.PositiveSmallIntegerField(
        default=8, help_text="Skills counted in general technical score."
    )
    recent_window = models.PositiveSmallIntegerField(default=3, help_text="Latest N assessments averaged.")
    project_target = models.PositiveSmallIntegerField(default=3, help_text="Projects needed for full project depth.")
    ready_threshold = models.PositiveSmallIntegerField(default=70, help_text="Readiness % at or above which = Ready.")
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "version"], name="readiness_config_version_unique"),
            models.UniqueConstraint(
                fields=["institution"], condition=models.Q(is_active=True), name="readiness_one_active_config"
            ),
        ]

    def __str__(self):
        return f"v{self.version}"

    @property
    def weights(self):
        return {
            "technical": self.weight_technical,
            "aptitude": self.weight_aptitude,
            "communication": self.weight_communication,
            "project_depth": self.weight_project_depth,
            "coding_activity": self.weight_coding,
        }


class ReadinessSnapshot(AppendOnlyModel):
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="readiness")
    drive = models.ForeignKey(
        "drives.Drive",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="Null for the general (role-agnostic) snapshot.",
    )
    config = models.ForeignKey(ScoringConfig, on_delete=models.PROTECT, related_name="+")
    technical = models.DecimalField(max_digits=5, decimal_places=2)
    aptitude = models.DecimalField(max_digits=5, decimal_places=2)
    communication = models.DecimalField(max_digits=5, decimal_places=2)
    project_depth = models.DecimalField(max_digits=5, decimal_places=2)
    coding_activity = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall = models.DecimalField(max_digits=5, decimal_places=2)
    explanation = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["student", "drive", "-created_at"])]

    def __str__(self):
        return f"{self.student_id}/{self.drive_id}: {self.overall}"
