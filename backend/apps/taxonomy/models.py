"""M1 Skill Taxonomy: the institution's controlled vocabulary for matching.

- Skill: a canonical skill. Abstract skills ("Frontend Framework") are skills too, so a
  requirement can name them.
- SkillSynonym: alternative spellings that resolve to one canonical skill ("Postgres").
- SkillRelation: "child satisfies parent" edges (React -> Frontend Framework). This is what
  taxonomy expansion uses during matching.
- SkillClosure: precomputed transitive closure of SkillRelation (maintained by services).
- SkillCluster: a reporting group (e.g. "Backend Development"); does not affect matching.
- TargetRole / RoleSkill: reusable role templates (software development, data, testing).
"""

from django.contrib.postgres.indexes import GinIndex
from django.db import models

from apps.core.models import TenantModel


class Level(models.IntegerChoices):
    """Ordinal proficiency scale shared by claims, requirements and gaps."""

    NONE = 0, "None"
    BEGINNER = 1, "Beginner"
    INTERMEDIATE = 2, "Intermediate"
    ADVANCED = 3, "Advanced"
    EXPERT = 4, "Expert"


POSITIVE_LEVEL_CHOICES = [(level.value, level.label) for level in Level if level > 0]


class SkillCluster(TenantModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["institution", "slug"], name="taxonomy_cluster_slug_unique")]

    def __str__(self):
        return self.name


class Skill(TenantModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120)
    normalized_name = models.CharField(max_length=120, editable=False)
    description = models.TextField(blank=True)
    cluster = models.ForeignKey(SkillCluster, null=True, blank=True, on_delete=models.SET_NULL, related_name="skills")
    is_abstract = models.BooleanField(
        default=False, help_text="A category such as 'Frontend Framework' that concrete skills satisfy."
    )
    is_active = models.BooleanField(default=True)
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "slug"], name="taxonomy_skill_slug_unique"),
            models.UniqueConstraint(
                fields=["institution", "normalized_name"], name="taxonomy_skill_normalized_name_unique"
            ),
        ]
        indexes = [GinIndex(name="taxonomy_skill_name_trgm", fields=["normalized_name"], opclasses=["gin_trgm_ops"])]

    def __str__(self):
        return self.name


class SkillSynonym(TenantModel):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="synonyms")
    name = models.CharField(max_length=120)
    normalized_name = models.CharField(max_length=120, editable=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "normalized_name"], name="taxonomy_synonym_normalized_name_unique"
            ),
        ]
        indexes = [GinIndex(name="taxonomy_synonym_name_trgm", fields=["normalized_name"], opclasses=["gin_trgm_ops"])]

    def __str__(self):
        return f"{self.name} -> {self.skill.name}"


class SkillRelation(TenantModel):
    """`child` satisfies a requirement for `parent`."""

    child = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="parent_links")
    parent = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="child_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["child", "parent"], name="taxonomy_relation_unique"),
            models.CheckConstraint(condition=~models.Q(child=models.F("parent")), name="taxonomy_relation_no_self"),
        ]

    def __str__(self):
        return f"{self.child.name} -> {self.parent.name}"


class SkillClosure(models.Model):
    """Every (ancestor, descendant) pair, including each skill with itself at depth 0."""

    ancestor = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="descendant_links")
    descendant = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="ancestor_links")
    depth = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ancestor", "descendant"], name="taxonomy_closure_unique")]
        indexes = [models.Index(fields=["descendant", "ancestor"])]

    def __str__(self):
        return f"{self.descendant_id} -> {self.ancestor_id} ({self.depth})"


class TargetRole(TenantModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["institution", "slug"], name="taxonomy_role_slug_unique")]

    def __str__(self):
        return self.name


class RoleSkill(TenantModel):
    role = models.ForeignKey(TargetRole, on_delete=models.CASCADE, related_name="role_skills")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="role_links")
    required_level = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.INTERMEDIATE)
    weight = models.PositiveSmallIntegerField(default=1, help_text="Relative importance within the role.")
    is_core = models.BooleanField(default=False)

    class Meta:
        ordering = ["-weight", "skill__name"]
        constraints = [models.UniqueConstraint(fields=["role", "skill"], name="taxonomy_role_skill_unique")]

    def __str__(self):
        return f"{self.role.name}: {self.skill.name}"
