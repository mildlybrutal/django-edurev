"""M9 Preparation Planning: gaps -> dated tasks and checkpoints."""

from django.db import models

from apps.core.models import TenantModel
from apps.taxonomy.models import Level


class ResourceKind(models.TextChoices):
    COURSE = "course", "Course"
    DOCUMENTATION = "documentation", "Documentation"
    PRACTICE = "practice", "Practice"
    PROJECT = "project", "Project idea"
    VIDEO = "video", "Video"
    BOOK = "book", "Book"


class LearningResource(TenantModel):
    skill = models.ForeignKey("taxonomy.Skill", on_delete=models.CASCADE, related_name="+")
    target_level = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.INTERMEDIATE)
    title = models.CharField(max_length=200)
    url = models.URLField(blank=True)
    kind = models.CharField(max_length=20, choices=ResourceKind.choices, default=ResourceKind.DOCUMENTATION)
    estimated_hours = models.PositiveSmallIntegerField(default=6)

    class Meta:
        ordering = ["skill__name", "target_level"]

    def __str__(self):
        return self.title


class PlanStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class PreparationPlan(TenantModel):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="plans")
    drive = models.ForeignKey("drives.Drive", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ItemStatus(models.TextChoices):
    TODO = "todo", "To do"
    IN_PROGRESS = "in_progress", "In progress"
    DONE = "done", "Done"


class PlanItem(models.Model):
    plan = models.ForeignKey(PreparationPlan, on_delete=models.CASCADE, related_name="items")
    skill = models.ForeignKey("taxonomy.Skill", null=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    resource_title = models.CharField(max_length=200, blank=True)
    resource_url = models.URLField(blank=True)
    start_date = models.DateField()
    due_date = models.DateField()
    is_checkpoint = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=ItemStatus.choices, default=ItemStatus.TODO)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField()
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "order"]

    def __str__(self):
        return self.title
