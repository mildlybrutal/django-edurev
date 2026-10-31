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
