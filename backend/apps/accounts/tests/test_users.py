import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.roles import Role, has_role, user_roles

User = get_user_model()


def test_create_user_requires_email(db):
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x")


def test_create_user_normalizes_domain_and_hashes_password(institution):
    user = User.objects.create_user(email="Student@EXAMPLE.test", password="s3cret-pass", institution=institution)
    assert user.email == "Student@example.test"
    assert user.check_password("s3cret-pass")
    assert not user.is_staff and not user.is_superuser


def test_email_is_unique_case_insensitively(institution):
    User.objects.create_user(email="a@example.test", password="x", institution=institution)
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="A@example.test", password="x", institution=institution)


def test_non_superuser_must_belong_to_an_institution(db):
    user = User(email="orphan@example.test")
    with pytest.raises(ValidationError) as exc:
        user.full_clean()
    assert "institution" in exc.value.message_dict


def test_superuser_may_have_no_institution(db):
    admin = User.objects.create_superuser(email="root@example.test", password="x")
    admin.full_clean(exclude=["password"])
    assert admin.is_staff and admin.is_superuser


def test_every_role_group_exists_after_migrations(db):
    assert set(Group.objects.values_list("name", flat=True)) >= set(Role.values)


def test_has_role(institution):
    user = User.objects.create_user(email="officer@example.test", password="x", institution=institution)
    user.groups.add(Group.objects.get(name=Role.PLACEMENT_OFFICER))
    assert user_roles(user) == {"placement_officer"}
    assert has_role(user, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD)
    assert not has_role(user, Role.RECRUITER)
