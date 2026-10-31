import base64
import time

import pytest
from django.test import override_settings

from apps.accounts import totp
from apps.accounts.roles import Role
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    "at,expected", [(59, "94287082"), (1111111109, "07081804"), (1234567890, "89005924"), (2000000000, "69279037")]
)
def test_totp_matches_rfc6238_sha1_vectors(at, expected):
    assert totp.totp(RFC_SECRET, at=at, digits=8) == expected


def test_verify_accepts_clock_drift_and_rejects_replay():
    secret = totp.new_secret()
    now = 1_700_000_000
    code = totp.totp(secret, at=now - 30)
    counter = totp.verify(secret, code, at=now)
    assert counter == (now - 30) // 30
    assert totp.verify(secret, code, at=now, last_counter=counter) is None
    assert totp.verify(secret, "12345", at=now) is None
    assert totp.verify(secret, "abcdef", at=now) is None


def _enroll(client):
    secret = client.post("/api/v1/auth/mfa/setup/").json()["secret"]
    response = client.post("/api/v1/auth/mfa/confirm/", {"code": totp.totp(secret)}, format="json")
    assert response.status_code == 200, response.content
    return secret


def test_enrolled_user_needs_a_code_to_get_a_session(make_user, login, csrf_client):
    make_user(email="officer@example.test", roles=[Role.PLACEMENT_OFFICER])
    client = login("officer@example.test")
    secret = _enroll(client)
    client.post("/api/v1/auth/logout/")

    step1 = csrf_client.post(
        "/api/v1/auth/login/", {"email": "officer@example.test", "password": "Correct-Horse-9"}, format="json"
    )
    assert step1.json() == {"mfa_required": True}
    assert "pa_access" not in step1.cookies or step1.cookies["pa_access"].value == ""
    assert csrf_client.get("/api/v1/auth/me/").status_code == 401

    bad = csrf_client.post("/api/v1/auth/mfa/verify/", {"code": "000000"}, format="json")
    assert bad.status_code == 401
    # The current step's code was consumed by the confirm step (anti-replay), so use the next one.
    good = csrf_client.post("/api/v1/auth/mfa/verify/", {"code": totp.totp(secret, at=time.time() + 30)}, format="json")
    assert good.status_code == 200, good.content
    assert csrf_client.get("/api/v1/auth/me/").json()["mfa"]["enabled"] is True
    assert AuditLog.objects.filter(action="auth.login.internal.mfa").exists()


def test_verify_without_challenge_cookie_fails(csrf_client):
    assert csrf_client.post("/api/v1/auth/mfa/verify/", {"code": "123456"}, format="json").status_code == 401


def test_confirmed_device_cannot_be_silently_replaced(make_user, login):
    make_user(email="u@example.test", roles=[Role.STUDENT])
    client = login("u@example.test")
    _enroll(client)
    assert client.post("/api/v1/auth/mfa/setup/").status_code == 400


@override_settings(MFA_REQUIRED_ROLES=["admin"])
def test_required_role_gets_restricted_session_until_enrolled(make_user, login):
    make_user(email="adm@example.test", roles=[Role.ADMIN])
    client = login("adm@example.test")
    me = client.get("/api/v1/auth/me/").json()
    assert me["mfa"] == {"enabled": False, "setup_required": True}
    blocked = client.get("/api/v1/skills/")
    assert blocked.status_code == 403 and blocked.json()["detail"].startswith("Set up two-factor")
    _enroll(client)  # confirm re-issues a full session
    assert client.get("/api/v1/skills/").status_code == 200


@override_settings(MFA_REQUIRED_ROLES=["admin"])
def test_required_role_cannot_disable_mfa(make_user, login):
    make_user(email="adm@example.test", roles=[Role.ADMIN])
    client = login("adm@example.test")
    secret = _enroll(client)
    response = client.post("/api/v1/auth/mfa/disable/", {"code": totp.totp(secret, at=time.time() + 30)}, format="json")
    assert response.status_code == 400
