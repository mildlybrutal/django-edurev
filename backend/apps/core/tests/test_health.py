from unittest import mock

import pytest
from django.db.utils import OperationalError


def test_health_is_public_and_touches_no_dependencies(client):
    with mock.patch("apps.core.views.connection") as conn:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    conn.cursor.assert_not_called()


@pytest.mark.django_db
def test_ready_ok_when_database_and_cache_reachable(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": True, "cache": True}


@pytest.mark.django_db
def test_ready_503_when_database_unreachable(client):
    with mock.patch("apps.core.views.connection") as conn:
        conn.cursor.side_effect = OperationalError("down")
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False


def test_health_rejects_non_get(client):
    assert client.post("/health").status_code == 405


def test_health_answers_platform_checks_on_any_host_without_redirect(client, settings):
    """Render probes over plain HTTP with an internal Host; prod settings must not 400 or redirect it."""
    settings.ALLOWED_HOSTS = ["placement.example.edu"]
    settings.SECURE_SSL_REDIRECT = True
    response = client.get("/health", HTTP_HOST="10.0.0.12:8000")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    # Everything else still gets host validation.
    assert client.get("/ready", HTTP_HOST="10.0.0.12:8000").status_code == 400
