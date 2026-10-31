"""M4 Student Skill Profile: levelled skill claims derived from evidence, with provenance."""

from django.db import models

from apps.core.models import TenantModel
from apps.evidence.models import SourceType
from apps.taxonomy.models import Level


class EvidenceRule(TenantModel):
    """How much one evidence source can establish. Implementation policy, configurable per
    institution (docs/scoring-policy.md); not values from the P06 specification."""

    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    max_level_unverified = models.PositiveSmallIntegerField(
        choices=Level.choices, help_text="Highest level unverified evidence of this type can support."
    )
    max_level_verified = models.PositiveSmallIntegerField(
        choices=Level.choices, help_text="Highest level verified evidence of this type can support."
    )

    class Meta:
        ordering = ["source_type"]
        constraints = [models.UniqueConstraint(fields=["institution", "source_type"], name="profiles_rule_unique")]

    def __str__(self):
        return self.source_type


class SkillClaim(TenantModel):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="skill_claims")
    skill = models.ForeignKey("taxonomy.Skill", on_delete=models.CASCADE, related_name="+")
    level = models.PositiveSmallIntegerField(choices=Level.choices, help_text="Best level any evidence supports.")
    verified_level = models.PositiveSmallIntegerField(
        choices=Level.choices, default=Level.NONE, help_text="Best level supported by verified evidence alone."
    )
    evidence_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-level", "skill__name"]
        constraints = [models.UniqueConstraint(fields=["student", "skill"], name="profiles_claim_unique")]

    def __str__(self):
        return f"{self.student_id}:{self.skill_id}@{self.level}"

    @property
    def is_verified(self):
        return self.verified_level >= self.level and self.level > 0


class ClaimEvidence(models.Model):
    """Why a claim exists: each supporting evidence item and the level it was allowed to support."""

    claim = models.ForeignKey(SkillClaim, on_delete=models.CASCADE, related_name="supports")
    evidence = models.ForeignKey("evidence.EvidenceItem", on_delete=models.CASCADE, related_name="+")
    claimed_level = models.PositiveSmallIntegerField(choices=Level.choices)
    effective_level = models.PositiveSmallIntegerField(choices=Level.choices)
    verified = models.BooleanField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["claim", "evidence"], name="profiles_claim_evidence_unique")]

    def __str__(self):
        return f"{self.claim_id}<-{self.evidence_id}"
