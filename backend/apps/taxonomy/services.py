import re
from collections import defaultdict

import django.dispatch
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from .models import RoleSkill, Skill, SkillClosure, SkillRelation, SkillSynonym

# Sent after `source` has been merged into `target`. Apps that reference skills (evidence
# tags, requirements, claims) connect a receiver and re-point their own rows, so taxonomy
# never touches another app's tables.
skill_merged = django.dispatch.Signal()


class TaxonomyError(ValueError):
    pass


_WS = re.compile(r"\s+")


def normalize(name):
    """Comparison key for skill names and synonyms: case-folded, single-spaced, trimmed."""
    return _WS.sub(" ", name).strip().casefold()


def _name_taken(institution, normalized, *, exclude_skill=None, exclude_synonym=None):
    skills = Skill.objects.filter(institution=institution, normalized_name=normalized)
    synonyms = SkillSynonym.objects.filter(institution=institution, normalized_name=normalized)
    if exclude_skill is not None:
        skills = skills.exclude(pk=exclude_skill.pk)
    if exclude_synonym is not None:
        synonyms = synonyms.exclude(pk=exclude_synonym.pk)
    return skills.exists() or synonyms.exists()


def _unique_slug(institution, name, *, exclude_pk=None):
    base = slugify(name) or "skill"
    slug, n = base, 2
    existing = Skill.objects.filter(institution=institution)
    if exclude_pk is not None:
        existing = existing.exclude(pk=exclude_pk)
    while existing.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


@transaction.atomic
def create_skill(*, institution, name, description="", cluster=None, is_abstract=False, parents=(), rebuild=True):
    normalized = normalize(name)
    if not normalized:
        raise TaxonomyError("Skill name is required.")
    if _name_taken(institution, normalized):
        raise TaxonomyError(f"'{name}' is already a skill or synonym.")
    if cluster is not None and cluster.institution_id != institution.id:
        raise TaxonomyError("Cluster belongs to another institution.")
    skill = Skill.objects.create(
        institution=institution,
        name=name.strip(),
        slug=_unique_slug(institution, name),
        normalized_name=normalized,
        description=description,
        cluster=cluster,
        is_abstract=is_abstract,
    )
    for parent in parents:
        _add_relation_no_rebuild(skill, parent)
    if rebuild:
        rebuild_closure(institution)
    return skill


@transaction.atomic
def update_skill(skill, *, name=None, description=None, cluster=..., is_abstract=None):
    if name is not None and normalize(name) != skill.normalized_name:
        normalized = normalize(name)
        if not normalized:
            raise TaxonomyError("Skill name is required.")
        if _name_taken(skill.institution, normalized, exclude_skill=skill):
            raise TaxonomyError(f"'{name}' is already a skill or synonym.")
        skill.name, skill.normalized_name = name.strip(), normalized
        skill.slug = _unique_slug(skill.institution, name, exclude_pk=skill.pk)
    if description is not None:
        skill.description = description
    if cluster is not ...:
        if cluster is not None and cluster.institution_id != skill.institution_id:
            raise TaxonomyError("Cluster belongs to another institution.")
        skill.cluster = cluster
    if is_abstract is not None:
        skill.is_abstract = is_abstract
    skill.save()
    return skill


@transaction.atomic
def add_synonym(skill, name):
    normalized = normalize(name)
    if not normalized:
        raise TaxonomyError("Synonym is required.")
    if _name_taken(skill.institution, normalized):
        raise TaxonomyError(f"'{name}' is already a skill or synonym.")
    return SkillSynonym.objects.create(
        institution=skill.institution, skill=skill, name=name.strip(), normalized_name=normalized
    )


def remove_synonym(synonym):
    synonym.delete()


def _add_relation_no_rebuild(child, parent):
    if child.institution_id != parent.institution_id:
        raise TaxonomyError("Skills belong to different institutions.")
    if child.pk == parent.pk:
        raise TaxonomyError("A skill cannot satisfy itself.")
    if not (child.is_active and parent.is_active):
        raise TaxonomyError("Cannot link a merged or inactive skill.")
    # A cycle would appear if the new parent is already the child or one of its descendants.
    if _is_descendant(child.institution, parent.pk, of=child.pk):
        raise TaxonomyError(f"Linking {child.name} under {parent.name} would create a cycle.")
    relation, _ = SkillRelation.objects.get_or_create(institution=child.institution, child=child, parent=parent)
    return relation


def _is_descendant(institution, skill_id, *, of):
    """True if `skill_id` is `of` or lies below it. Reads relations directly rather than the
    closure, which may not be rebuilt yet inside a multi-step transaction."""
    children = defaultdict(set)
    for c, p in SkillRelation.objects.filter(institution=institution).values_list("child_id", "parent_id"):
        children[p].add(c)
    stack, seen = [of], set()
    while stack:
        node = stack.pop()
        if node == skill_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(children[node])
    return False


@transaction.atomic
def add_relation(child, parent, *, rebuild=True):
    """Record that `child` satisfies `parent`. Pass rebuild=False when adding many links,
    then call rebuild_closure once."""
    relation = _add_relation_no_rebuild(child, parent)
    if rebuild:
        rebuild_closure(child.institution)
    return relation


@transaction.atomic
def remove_relation(child, parent):
    SkillRelation.objects.filter(child=child, parent=parent).delete()
    rebuild_closure(child.institution)


@transaction.atomic
def rebuild_closure(institution):
    """Recompute SkillClosure for one institution. Taxonomies are small (hundreds of skills),
    so a full rebuild on each structural edit is simple and fast enough."""
    skill_ids = list(Skill.objects.filter(institution=institution).values_list("id", flat=True))
    parents = defaultdict(set)
    for c, p in SkillRelation.objects.filter(institution=institution).values_list("child_id", "parent_id"):
        parents[c].add(p)

    rows = []
    for skill_id in skill_ids:
        depth_of = {skill_id: 0}
        frontier = [skill_id]
        while frontier:
            nxt = []
            for node in frontier:
                for parent in parents[node]:
                    if parent not in depth_of:
                        depth_of[parent] = depth_of[node] + 1
                        nxt.append(parent)
            frontier = nxt
        rows.extend(SkillClosure(ancestor_id=a, descendant_id=skill_id, depth=d) for a, d in depth_of.items())

    SkillClosure.objects.filter(descendant__institution=institution).delete()
    SkillClosure.objects.bulk_create(rows, batch_size=1000)


@transaction.atomic
def merge_skills(source, target):
    """Fold `source` into `target`: its name and synonyms become synonyms of `target`, its
    relations and role links move across, and `source` is kept but deactivated for history."""
    if source.pk == target.pk:
        raise TaxonomyError("Cannot merge a skill into itself.")
    if source.institution_id != target.institution_id:
        raise TaxonomyError("Skills belong to different institutions.")
    if not (source.is_active and target.is_active):
        raise TaxonomyError("Both skills must be active.")

    SkillSynonym.objects.filter(skill=source).update(skill=target)

    for relation in SkillRelation.objects.filter(child=source):
        if (
            relation.parent_id != target.pk
            and not SkillRelation.objects.filter(child=target, parent_id=relation.parent_id).exists()
        ):
            SkillRelation.objects.create(institution=source.institution, child=target, parent_id=relation.parent_id)
    for relation in SkillRelation.objects.filter(parent=source):
        if (
            relation.child_id != target.pk
            and not SkillRelation.objects.filter(child_id=relation.child_id, parent=target).exists()
        ):
            SkillRelation.objects.create(institution=source.institution, child_id=relation.child_id, parent=target)
    SkillRelation.objects.filter(Q(child=source) | Q(parent=source)).delete()

    for link in RoleSkill.objects.filter(skill=source):
        existing = RoleSkill.objects.filter(role=link.role, skill=target).first()
        if existing:
            existing.required_level = max(existing.required_level, link.required_level)
            existing.weight = max(existing.weight, link.weight)
            existing.is_core = existing.is_core or link.is_core
            existing.save()
            link.delete()
        else:
            link.skill = target
            link.save()

    # The source's own name must be freed before it can be re-registered as a synonym.
    source_name, source_normalized = source.name, source.normalized_name
    source.is_active = False
    source.merged_into = target
    source.normalized_name = f"__merged__{source.pk}"
    source.save()
    SkillSynonym.objects.create(
        institution=source.institution, skill=target, name=source_name, normalized_name=source_normalized
    )

    rebuild_closure(source.institution)
    skill_merged.send(sender=Skill, source=source, target=target)
    return target
