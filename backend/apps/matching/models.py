"""M8 Match & Gap Analysis. Compatibility (skill match against a drive's requirements) is stored
here; eligibility lives in drives.EligibilityResult and is never merged into these numbers."""

from django.db import models

from apps.core.models import TenantModel
from apps.taxonomy.models import Level


class MatchResult(TenantModel):
    drive = models.ForeignKey("drives.Drive", on_delete=models.CASCADE, related_name="match_results")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="match_results")
    compatibility = models.DecimalField(max_digits=5, decimal_places=2)
    breakdown = models.JSONField(help_text="Per-requirement explanation of the compatibility score.")
    readiness_overall = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    readiness_snapshot = models.ForeignKey(
        "readiness.ReadinessSnapshot", null=True, on_delete=models.SET_NULL, related_name="+"
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["drive", "student"], name="matching_result_unique")]
        indexes = [models.Index(fields=["drive", "-compatibility"])]


class GapKind(models.TextChoices):
    MISSING = "missing", "No evidence"
    BELOW_LEVEL = "below_level", "Below required level"
    UNVERIFIED = "unverified", "Not verified"


class Impact(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class GapAnalysis(TenantModel):
    drive = models.ForeignKey("drives.Drive", on_delete=models.CASCADE, related_name="gap_analyses")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="gap_analyses")
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["drive", "student"], name="matching_gap_analysis_unique")]


class GapItem(models.Model):
    analysis = models.ForeignKey(GapAnalysis, on_delete=models.CASCADE, related_name="items")
    skill = models.ForeignKey("taxonomy.Skill", on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=20, choices=GapKind.choices)
    current_level = models.PositiveSmallIntegerField(choices=Level.choices)
    verified_level = models.PositiveSmallIntegerField(choices=Level.choices)
    required_level = models.PositiveSmallIntegerField(choices=Level.choices)
    is_mandatory = models.BooleanField()
    weight = models.PositiveSmallIntegerField()
    impact_score = models.DecimalField(max_digits=6, decimal_places=3)
    impact = models.CharField(max_length=10, choices=Impact.choices)
    rank = models.PositiveSmallIntegerField()
    suggested_action = models.TextField()

    class Meta:
        ordering = ["rank"]
        indexes = [models.Index(fields=["skill", "kind"])]

    def __str__(self):
        return f"#{self.rank} {self.skill_id} ({self.kind})"
