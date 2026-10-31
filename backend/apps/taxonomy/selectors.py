"""Read-side functions other apps use to query the taxonomy."""

from collections import defaultdict

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Exists, FloatField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, Greatest

from .models import Skill, SkillClosure, SkillSynonym
from .services import normalize


def active_skills(institution):
    return Skill.objects.filter(institution=institution, is_active=True)


def resolve_skill(institution, text):
    """Map free text to a canonical active skill via exact name or synonym match, else None."""
    key = normalize(text)
    if not key:
        return None
    skill = active_skills(institution).filter(normalized_name=key).first()
    if skill:
        return skill
    synonym = (
        SkillSynonym.objects.filter(institution=institution, normalized_name=key, skill__is_active=True)
        .select_related("skill")
        .first()
    )
    return synonym.skill if synonym else None


def search_skills(institution, query, *, limit=20, min_similarity=0.2):
    """Fuzzy search over names and synonyms (pg_trgm), best match first."""
    key = normalize(query)
    qs = active_skills(institution).select_related("cluster")
    if not key:
        return qs.order_by("name")[:limit]
    synonyms = SkillSynonym.objects.filter(skill=OuterRef("pk"))
    best_synonym_sim = (
        synonyms.annotate(sim=TrigramSimilarity("normalized_name", key)).order_by("-sim").values("sim")[:1]
    )
    return (
        qs.annotate(
            score=Greatest(
                TrigramSimilarity("normalized_name", key),
                Coalesce(Subquery(best_synonym_sim, output_field=FloatField()), Value(0.0)),
            ),
            synonym_contains=Exists(synonyms.filter(normalized_name__contains=key)),
        )
        .filter(Q(score__gte=min_similarity) | Q(normalized_name__contains=key) | Q(synonym_contains=True))
        .order_by("-score", "name")[:limit]
    )


def ancestor_map(skill_ids):
    """{skill_id: {ancestor ids including itself}}: every requirement each skill can satisfy."""
    result = defaultdict(set)
    for ancestor, descendant in SkillClosure.objects.filter(descendant_id__in=skill_ids).values_list(
        "ancestor_id", "descendant_id"
    ):
        result[descendant].add(ancestor)
    return result


def satisfying_skill_ids(required_skill_id):
    """Ids of skills that satisfy a requirement: the skill itself plus everything below it."""
    return set(SkillClosure.objects.filter(ancestor_id=required_skill_id).values_list("descendant_id", flat=True))


def satisfaction_depth(student_skill_id, required_skill_id):
    """0 for an exact match, n for a taxonomy-expanded match n levels down, None for no match."""
    return (
        SkillClosure.objects.filter(ancestor_id=required_skill_id, descendant_id=student_skill_id)
        .values_list("depth", flat=True)
        .first()
    )
