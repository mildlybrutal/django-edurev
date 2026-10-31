"""Coding activity profiles. A rating summarises public activity; it is evidence, not proof of
expertise (AGENTS.md §3), and is always shown as unverified external evidence."""

from django.db import models

from apps.core.models import TenantModel


class Platform(models.TextChoices):
    GITHUB = "github", "GitHub"
    LEETCODE = "leetcode", "LeetCode"


class SyncStatus(models.TextChoices):
    PENDING = "pending", "Waiting to sync"
    OK = "ok", "Synced"
    NOT_FOUND = "not_found", "Profile not found"
    ERROR = "error", "Could not reach the platform"


class CodingProfile(TenantModel):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="coding_profiles")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    username = models.CharField(max_length=60)
    status = models.CharField(max_length=20, choices=SyncStatus.choices, default=SyncStatus.PENDING)
    stats = models.JSONField(default=dict, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    explanation = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=300, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    evidence = models.ForeignKey(
        "evidence.EvidenceItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["platform"]
        constraints = [models.UniqueConstraint(fields=["student", "platform"], name="coding_profile_unique")]

    def __str__(self):
        return f"{self.platform}:{self.username}"
