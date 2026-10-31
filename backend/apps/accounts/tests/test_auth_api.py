import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.roles import Role
from apps.accounts.services import issue_tokens
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"


def test_login_sets_httponly_cookies_and_returns_profile(csrf_client, student):
    response = csrf_client.post(LOGIN, {"email": student.email, "password": "Correct-Horse-9"}, format="json")

    assert response.status_code == 200
    assert response.json()["roles"] == ["student"]
    access, refresh = response.cookies["pa_access"], response.cookies["pa_refresh"]
    assert access["httponly"] and refresh["httponly"]
    assert refresh["path"] == "/api/v1/auth/"
    assert "access" not in response.json() and "refresh" not in response.json()


def test_login_email_is_case_insensitive(csrf_client, student):
    response = csrf_client.post(LOGIN, {"email": "STUDENT@example.test", "password": "Correct-Horse-9"}, format="json")
    assert response.status_code == 200


def test_login_wrong_password_and_unknown_email_look_identical(csrf_client, student):
    wrong = csrf_client.post(LOGIN, {"email": student.email, "password": "nope"}, format="json")
    unknown = csrf_client.post(LOGIN, {"email": "ghost@example.test", "password": "nope"}, format="json")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_requires_csrf_token(student):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(LOGIN, {"email": student.email, "password": "Correct-Horse-9"}, format="json")
    assert response.status_code == 403


@override_settings(LOGIN_LOCKOUT_THRESHOLD=3)
def test_lockout_after_repeated_failures_even_with_correct_password(csrf_client, student):
    for _ in range(3):
        assert csrf_client.post(LOGIN, {"email": student.email, "password": "bad"}, format="json").status_code == 401
    response = csrf_client.post(LOGIN, {"email": student.email, "password": "Correct-Horse-9"}, format="json")
    assert response.status_code == 429


def test_inactive_user_cannot_login(csrf_client, make_user):
    user = make_user(email="gone@example.test", roles=[Role.STUDENT], is_active=False)
    response = csrf_client.post(LOGIN, {"email": user.email, "password": "Correct-Horse-9"}, format="json")
    assert response.status_code == 401


def test_recruiter_cannot_login_to_internal_portal(csrf_client, make_user):
    recruiter = make_user(email="rec@example.test", roles=[Role.RECRUITER])
    response = csrf_client.post(LOGIN, {"email": recruiter.email, "password": "Correct-Horse-9"}, format="json")
    assert response.status_code == 401


def test_me_requires_authentication():
    assert APIClient().get(ME).status_code == 401


def test_me_returns_current_user(login, student):
    client = login(student.email)
    body = client.get(ME).json()
    assert body["email"] == student.email
    assert body["institution"]["code"] == "synthetic-u"


def test_recruiter_portal_token_rejected_on_internal_endpoints(make_user):
    recruiter = make_user(email="rec@example.test", roles=[Role.RECRUITER])
    tokens = issue_tokens(recruiter, "recruiter")
    client = APIClient()
    client.cookies["pa_access"] = tokens.access  # replayed under the internal cookie name
    assert client.get(ME).status_code == 401


def test_bearer_header_is_not_accepted(student):
    tokens = issue_tokens(student, "internal")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.access}")
    assert client.get(ME).status_code == 401


def test_unsafe_request_with_cookie_auth_requires_csrf(student):
    tokens = issue_tokens(student, "internal")
    client = APIClient(enforce_csrf_checks=True)
    client.cookies["pa_access"] = tokens.access
    # GET is allowed without CSRF; an unsafe method on an authenticated endpoint is not.
    assert client.get(ME).status_code == 200
    assert client.post(ME, {}, format="json").status_code == 403


def test_refresh_rotates_and_old_refresh_token_is_blacklisted(login, student):
    client = login(student.email)
    old_refresh = client.cookies["pa_refresh"].value

    response = client.post(REFRESH)
    assert response.status_code == 204
    assert response.cookies["pa_refresh"].value != old_refresh

    client.cookies["pa_refresh"] = old_refresh
    assert client.post(REFRESH).status_code == 401


def test_logout_clears_cookies_and_revokes_refresh(login, student):
    client = login(student.email)
    refresh = client.cookies["pa_refresh"].value

    response = client.post(LOGOUT)
    assert response.status_code == 204
    assert response.cookies["pa_access"].value == ""

    client.cookies["pa_refresh"] = refresh
    assert client.post(REFRESH).status_code == 401


def test_login_and_logout_are_audited_without_personal_data(login, student):
    client = login(student.email)
    client.post(LOGOUT)
    actions = list(AuditLog.objects.order_by("created_at").values_list("action", "actor_id"))
    assert actions == [("auth.login.internal", student.id), ("auth.logout", student.id)]
    assert not AuditLog.objects.filter(after__icontains=student.email).exists()


def test_login_from_trusted_frontend_origin_succeeds(csrf_client, student):
    # Browsers send Origin on POST; through the Next.js proxy it differs from Django's host.
    response = csrf_client.post(
        LOGIN,
        {"email": student.email, "password": "Correct-Horse-9"},
        format="json",
        HTTP_ORIGIN="http://localhost:3000",
    )
    assert response.status_code == 200


def test_login_from_untrusted_origin_is_rejected(csrf_client, student):
    response = csrf_client.post(
        LOGIN,
        {"email": student.email, "password": "Correct-Horse-9"},
        format="json",
        HTTP_ORIGIN="https://evil.example",
    )
    assert response.status_code == 403
