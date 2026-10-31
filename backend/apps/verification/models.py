"""M3 Evidence Verification: an immutable record of each faculty decision."""

from django.db import models

from apps.core.models import AppendOnlyModel, Institution


class Decision(models.TextChoices):
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class Verification(AppendOnlyModel):
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="+")
    evidence = models.ForeignKey("evidence.EvidenceItem", on_delete=models.CASCADE, related_name="verifications")
    reviewer = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    decision = models.CharField(max_length=10, choices=Decision.choices)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.evidence_id} {self.decision}"
