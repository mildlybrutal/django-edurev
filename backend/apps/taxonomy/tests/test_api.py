import pytest

from apps.accounts.roles import Role
from apps.core.models import AuditLog, Institution
from apps.taxonomy import services
from apps.taxonomy.models import Skill

pytestmark = pytest.mark.django_db

SKILLS = "/api/v1/skills/"


@pytest.fixture
def admin_client(make_user, login):
    make_user(email="admin@example.test", roles=[Role.ADMIN])
    return login("admin@example.test")


@pytest.fixture
def student_client(make_user, login):
    make_user(email="student@example.test", roles=[Role.STUDENT])
    return login("student@example.test")


def test_anonymous_cannot_read_skills(client):
    assert client.get(SKILLS).status_code == 401


def test_student_can_read_and_search(student_client, institution):
    services.create_skill(institution=institution, name="Django")
    assert student_client.get(SKILLS).json()["count"] == 1
    assert student_client.get(SKILLS, {"q": "djang"}).json()["results"][0]["name"] == "Django"


@pytest.mark.parametrize("role", [Role.STUDENT, Role.FACULTY, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD])
def test_non_admin_roles_cannot_change_taxonomy(make_user, login, role, institution):
    make_user(email=f"{role}@example.test", roles=[role])
    client = login(f"{role}@example.test")
    skill = services.create_skill(institution=institution, name="Django")
    assert client.post(SKILLS, {"name": "Flask"}, format="json").status_code == 403
    assert client.patch(f"{SKILLS}{skill.pk}/", {"name": "X"}, format="json").status_code == 403
    assert client.post(f"{SKILLS}{skill.pk}/synonyms/", {"name": "dj"}, format="json").status_code == 403
    assert client.delete(f"{SKILLS}{skill.pk}/").status_code == 403


def test_admin_creates_skill_with_parent_and_synonym(admin_client, institution):
    parent = services.create_skill(institution=institution, name="Backend Framework", is_abstract=True)
    response = admin_client.post(SKILLS, {"name": "Django", "parent_ids": [parent.pk]}, format="json")
    assert response.status_code == 201, response.content
    skill_id = response.json()["id"]
    assert response.json()["parents"] == [{"id": parent.pk, "name": "Backend Framework", "slug": "backend-framework"}]

    response = admin_client.post(f"{SKILLS}{skill_id}/synonyms/", {"name": "Django Framework"}, format="json")
    assert response.status_code == 201
    assert admin_client.get(f"{SKILLS}resolve/", {"name": "django framework"}).json()["id"] == skill_id
    assert AuditLog.objects.filter(action="taxonomy.skill.create").exists()
    assert AuditLog.objects.filter(action="taxonomy.synonym.add").exists()


def test_duplicate_name_returns_400(admin_client, institution):
    services.create_skill(institution=institution, name="Django")
    response = admin_client.post(SKILLS, {"name": "django"}, format="json")
    assert response.status_code == 400


def test_cycle_returns_400(admin_client, institution):
    a = services.create_skill(institution=institution, name="A")
    b = services.create_skill(institution=institution, name="B", parents=[a])
    assert admin_client.post(f"{SKILLS}{a.pk}/parents/", {"skill_id": b.pk}, format="json").status_code == 400


def test_other_institution_skills_are_invisible(admin_client):
    other = Institution.objects.create(name="Other", code="other")
    foreign = services.create_skill(institution=other, name="Kubernetes")
    assert admin_client.get(f"{SKILLS}{foreign.pk}/").status_code == 404
    assert admin_client.patch(f"{SKILLS}{foreign.pk}/", {"name": "x"}, format="json").status_code == 404
    assert admin_client.get(SKILLS).json()["count"] == 0


def test_cannot_link_to_another_institutions_skill(admin_client, institution):
    other = Institution.objects.create(name="Other", code="other")
    foreign = services.create_skill(institution=other, name="Kubernetes")
    mine = services.create_skill(institution=institution, name="Docker")
    response = admin_client.post(f"{SKILLS}{mine.pk}/parents/", {"skill_id": foreign.pk}, format="json")
    assert response.status_code == 404


def test_delete_retires_skill_instead_of_removing_it(admin_client, institution):
    skill = services.create_skill(institution=institution, name="Flash")
    assert admin_client.delete(f"{SKILLS}{skill.pk}/").status_code == 204
    assert Skill.objects.filter(pk=skill.pk, is_active=False).exists()
    assert admin_client.get(f"{SKILLS}{skill.pk}/").status_code == 404


def test_merge_endpoint(admin_client, institution):
    a = services.create_skill(institution=institution, name="ReactJS Library")
    b = services.create_skill(institution=institution, name="React")
    response = admin_client.post(f"{SKILLS}{a.pk}/merge/", {"skill_id": b.pk}, format="json")
    assert response.status_code == 200
    assert {"name": "ReactJS Library"} in [{"name": s["name"]} for s in response.json()["synonyms"]]


def test_target_role_skill_mapping(admin_client, institution):
    skill = services.create_skill(institution=institution, name="SQL")
    role = admin_client.post(f"{SKILLS}roles/", {"name": "Data Analyst"}, format="json").json()
    response = admin_client.post(
        f"{SKILLS}roles/{role['id']}/skills/",
        {"skill_id": skill.pk, "required_level": 2, "weight": 5, "is_core": True},
        format="json",
    )
    assert response.status_code == 201
    mapped = response.json()["role_skills"][0]
    assert (mapped["skill"]["name"], mapped["required_level_label"], mapped["weight"]) == ("SQL", "Intermediate", 5)
