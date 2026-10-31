from django.db import transaction
from django.utils.text import slugify

from . import services
from .models import RoleSkill, Skill, SkillCluster, SkillSynonym, TargetRole
from .seed_data import CLUSTERS, ROLES, SKILLS


@transaction.atomic
def seed_taxonomy(institution):
    """Idempotently load the starter taxonomy. Existing names, synonyms and links are kept;
    only missing items are added, so re-running never overwrites an administrator's edits."""
    clusters = {}
    for slug, name in CLUSTERS.items():
        clusters[slug], _ = SkillCluster.objects.get_or_create(
            institution=institution, slug=slug, defaults={"name": name}
        )

    skills = {}
    for name, (cluster_slug, is_abstract, _, _) in SKILLS.items():
        existing = Skill.objects.filter(institution=institution, normalized_name=services.normalize(name)).first()
        if existing is None and services.normalize(name) in _synonym_keys(institution):
            continue  # an administrator has made this name a synonym of another skill
        skills[name] = existing or services.create_skill(
            institution=institution, name=name, cluster=clusters[cluster_slug], is_abstract=is_abstract, rebuild=False
        )

    taken = _synonym_keys(institution) | set(
        Skill.objects.filter(institution=institution).values_list("normalized_name", flat=True)
    )
    for name, (_, _, synonyms, _) in SKILLS.items():
        if name not in skills:
            continue
        for synonym in synonyms:
            if services.normalize(synonym) not in taken:
                services.add_synonym(skills[name], synonym)
                taken.add(services.normalize(synonym))

    for name, (_, _, _, parents) in SKILLS.items():
        for parent in parents:
            if name in skills and parent in skills:
                services.add_relation(skills[name], skills[parent], rebuild=False)
    services.rebuild_closure(institution)

    for role_name, (description, requirements) in ROLES.items():
        role, _ = TargetRole.objects.get_or_create(
            institution=institution, slug=slugify(role_name), defaults={"name": role_name, "description": description}
        )
        for skill_name, level, weight, is_core in requirements:
            if skill_name in skills:
                RoleSkill.objects.get_or_create(
                    institution=institution,
                    role=role,
                    skill=skills[skill_name],
                    defaults={"required_level": level, "weight": weight, "is_core": is_core},
                )
    return {"clusters": len(clusters), "skills": len(skills), "roles": len(ROLES)}


def _synonym_keys(institution):
    return set(SkillSynonym.objects.filter(institution=institution).values_list("normalized_name", flat=True))
