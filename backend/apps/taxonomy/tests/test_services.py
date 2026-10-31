import pytest

from apps.core.models import Institution
from apps.taxonomy import selectors, services
from apps.taxonomy.models import RoleSkill, Skill, SkillClosure, TargetRole
from apps.taxonomy.seed_data import ROLES
from apps.taxonomy.seeding import seed_taxonomy
from apps.taxonomy.services import TaxonomyError

pytestmark = pytest.mark.django_db


@pytest.fixture
def skill(institution):
    def _make(name, **kwargs):
        return services.create_skill(institution=institution, name=name, **kwargs)

    return _make


def test_normalize_collapses_case_and_whitespace():
    assert services.normalize("  Node   JS ") == "node js"


def test_skill_names_are_unique_case_insensitively(skill):
    skill("PostgreSQL")
    with pytest.raises(TaxonomyError):
        skill("postgresql")


def test_synonym_resolves_to_canonical_skill(institution, skill):
    postgres = skill("PostgreSQL")
    services.add_synonym(postgres, "Postgres")
    assert selectors.resolve_skill(institution, "postgres") == postgres
    assert selectors.resolve_skill(institution, "PostgreSQL") == postgres
    assert selectors.resolve_skill(institution, "Oracle") is None


def test_synonym_cannot_shadow_an_existing_skill_or_synonym(skill):
    react, vue = skill("React"), skill("Vue")
    services.add_synonym(react, "ReactJS")
    with pytest.raises(TaxonomyError):
        services.add_synonym(vue, "reactjs")
    with pytest.raises(TaxonomyError):
        services.add_synonym(vue, "React")


def test_taxonomy_expansion_through_closure(skill):
    framework = skill("Frontend Framework", is_abstract=True)
    react = skill("React", parents=[framework])
    nextjs = skill("Next.js", parents=[react])

    assert selectors.satisfying_skill_ids(framework.pk) == {framework.pk, react.pk, nextjs.pk}
    assert selectors.satisfaction_depth(react.pk, framework.pk) == 1
    assert selectors.satisfaction_depth(nextjs.pk, framework.pk) == 2
    assert selectors.satisfaction_depth(framework.pk, framework.pk) == 0
    # Expansion is one-directional: knowing "Frontend Framework" does not imply React.
    assert selectors.satisfaction_depth(framework.pk, react.pk) is None


def test_cycles_are_rejected(skill):
    a = skill("A")
    b = skill("B", parents=[a])
    c = skill("C", parents=[b])
    with pytest.raises(TaxonomyError):
        services.add_relation(a, c)
    with pytest.raises(TaxonomyError):
        services.add_relation(a, a)


def test_removing_a_relation_updates_the_closure(skill):
    framework = skill("Frontend Framework", is_abstract=True)
    react = skill("React", parents=[framework])
    services.remove_relation(react, framework)
    assert selectors.satisfaction_depth(react.pk, framework.pk) is None


def test_cross_institution_links_are_rejected(skill):
    other = Institution.objects.create(name="Other", code="other")
    foreign = services.create_skill(institution=other, name="React")
    with pytest.raises(TaxonomyError):
        services.add_relation(skill("Vue"), foreign)


def test_search_matches_fuzzy_names_and_synonyms(institution, skill):
    postgres = skill("PostgreSQL")
    services.add_synonym(postgres, "Postgres")
    skill("MongoDB")
    names = [s.name for s in selectors.search_skills(institution, "postgress")]
    assert names[0] == "PostgreSQL"
    assert "MongoDB" not in names


def test_search_is_scoped_to_institution(institution, skill):
    other = Institution.objects.create(name="Other", code="other")
    services.create_skill(institution=other, name="Kubernetes")
    assert list(selectors.search_skills(institution, "kubernetes")) == []


def test_merge_moves_synonyms_relations_and_roles(institution, skill):
    db = skill("SQL Database", is_abstract=True)
    postgres = skill("PostgreSQL", parents=[db])
    pg = skill("Postgres SQL", parents=[db])
    services.add_synonym(pg, "PG")
    role = TargetRole.objects.create(institution=institution, name="Backend", slug="backend")
    RoleSkill.objects.create(institution=institution, role=role, skill=pg, required_level=3, weight=4)

    received = []
    services.skill_merged.connect(lambda **kw: received.append((kw["source"].pk, kw["target"].pk)), weak=False)
    services.merge_skills(pg, postgres)

    pg.refresh_from_db()
    assert not pg.is_active and pg.merged_into == postgres
    assert selectors.resolve_skill(institution, "PG") == postgres
    assert selectors.resolve_skill(institution, "Postgres SQL") == postgres
    assert RoleSkill.objects.get(role=role).skill == postgres
    assert selectors.satisfaction_depth(postgres.pk, db.pk) == 1
    assert received == [(pg.pk, postgres.pk)]


def test_merged_skill_is_not_found_by_search(institution, skill):
    a, b = skill("Javascript Basics"), skill("JavaScript")
    services.merge_skills(a, b)
    assert [s.name for s in selectors.search_skills(institution, "javascript")] == ["JavaScript"]


def test_seed_creates_three_target_roles_and_is_idempotent(institution):
    first = seed_taxonomy(institution)
    skills_after_first = Skill.objects.filter(institution=institution).count()
    closure_after_first = SkillClosure.objects.count()
    second = seed_taxonomy(institution)

    assert first == second
    assert Skill.objects.filter(institution=institution).count() == skills_after_first
    assert SkillClosure.objects.count() == closure_after_first
    assert set(TargetRole.objects.filter(institution=institution).values_list("name", flat=True)) == set(ROLES)
    for role in TargetRole.objects.filter(institution=institution):
        assert role.role_skills.count() >= 8


def test_seed_supports_taxonomy_expanded_matching(institution):
    seed_taxonomy(institution)
    react = selectors.resolve_skill(institution, "ReactJS")
    framework = selectors.resolve_skill(institution, "Frontend Framework")
    postgres = selectors.resolve_skill(institution, "Postgres")
    sql_db = selectors.resolve_skill(institution, "RDBMS")
    assert selectors.satisfaction_depth(react.pk, framework.pk) == 1
    assert selectors.satisfaction_depth(postgres.pk, sql_db.pk) == 1
