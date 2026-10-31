import pytest
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.accounts.permissions import SameInstitution, roles_required
from apps.accounts.roles import Role
from apps.core.models import Institution

pytestmark = pytest.mark.django_db


class OfficerOnlyView(APIView):
    permission_classes = [roles_required(Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD)]

    def get(self, request):
        return Response({"ok": True})


def _get(user):
    request = APIRequestFactory().get("/probe")
    force_authenticate(request, user=user)
    return OfficerOnlyView.as_view()(request)


def test_role_permission_allows_listed_roles(make_user):
    assert _get(make_user(email="o@example.test", roles=[Role.PLACEMENT_OFFICER])).status_code == 200
    assert _get(make_user(email="h@example.test", roles=[Role.PLACEMENT_HEAD])).status_code == 200


@pytest.mark.parametrize("role", [Role.STUDENT, Role.FACULTY, Role.RECRUITER, Role.ADMIN])
def test_role_permission_denies_other_roles(make_user, role):
    assert _get(make_user(email=f"{role}@example.test", roles=[role])).status_code == 403


def test_role_permission_denies_user_without_roles(make_user):
    assert _get(make_user(email="none@example.test")).status_code == 403


def test_same_institution_object_check(make_user, institution):
    user = make_user(email="o@example.test")
    other = Institution.objects.create(name="Other", code="other")
    permission = SameInstitution()
    request = type("R", (), {"user": user})()
    assert permission.has_object_permission(request, None, type("O", (), {"institution_id": institution.id})())
    assert not permission.has_object_permission(request, None, type("O", (), {"institution_id": other.id})())
