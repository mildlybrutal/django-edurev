"""M5 Assessment & Mock Interview: rubric-based evaluations with full history."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TenantModel
from apps.taxonomy.models import Level


class AssessmentKind(models.TextChoices):
    TECHNICAL = "technical", "Technical"
    APTITUDE = "aptitude", "Aptitude"
    COMMUNICATION = "communication", "Communication"


class Rubric(TenantModel):
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=AssessmentKind.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name

    @property
    def max_total(self):
        return sum(c.max_score for c in self.criteria.all())


class RubricCriterion(models.Model):
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name="criteria")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    max_score = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1)])
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Assessment(TenantModel):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="assessments")
    rubric = models.ForeignKey(Rubric, on_delete=models.PROTECT, related_name="assessments")
    kind = models.CharField(max_length=20, choices=AssessmentKind.choices)
    title = models.CharField(max_length=200)
    skill = models.ForeignKey(
        "taxonomy.Skill",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="For technical assessments: the skill assessed.",
    )
    assessed_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    assessed_on = models.DateField()
    total_score = models.DecimalField(max_digits=7, decimal_places=2)
    max_score = models.DecimalField(max_digits=7, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)
    evidence = models.OneToOneField(
        "evidence.EvidenceItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="assessment"
    )

    class Meta:
        ordering = ["-assessed_on", "-id"]

    def __str__(self):
        return self.title


class AssessmentScore(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="scores")
    criterion = models.ForeignKey(RubricCriterion, on_delete=models.PROTECT, related_name="+")
    score = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "criterion"], name="assessment_score_unique")]

    def __str__(self):
        return f"{self.criterion_id}: {self.score}"


class MockInterview(TenantModel):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="mock_interviews")
    interviewer = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    conducted_on = models.DateField()
    role_focus = models.CharField(max_length=150, blank=True, help_text="e.g. Backend Engineer")
    technical_score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    communication_score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    problem_solving_score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    feedback = models.TextField(blank=True)
    evidence = models.OneToOneField(
        "evidence.EvidenceItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="mock_interview"
    )

    class Meta:
        ordering = ["-conducted_on", "-id"]

    def __str__(self):
        return f"Mock interview {self.student_id} {self.conducted_on}"


class MockInterviewSkillRating(models.Model):
    interview = models.ForeignKey(MockInterview, on_delete=models.CASCADE, related_name="skill_ratings")
    skill = models.ForeignKey("taxonomy.Skill", on_delete=models.PROTECT, related_name="+")
    level = models.PositiveSmallIntegerField(choices=Level.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["interview", "skill"], name="mock_rating_unique")]

    def __str__(self):
        return f"{self.skill_id}@{self.level}"
