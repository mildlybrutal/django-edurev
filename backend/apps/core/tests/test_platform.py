import pytest
from django.db import IntegrityError

from apps.core.models import Institution
from apps.core.tasks import ping


@pytest.mark.django_db
def test_institution_code_is_unique():
    Institution.objects.create(name="Synthetic University", code="synthetic-u")
    with pytest.raises(IntegrityError):
        Institution.objects.create(name="Another", code="synthetic-u")


def test_celery_ping_task_runs():
    assert ping.delay().get(timeout=5) == "pong"


@pytest.mark.django_db
def test_openapi_schema_served_under_api_v1(client):
    response = client.get("/api/v1/schema/")
    assert response.status_code == 200
    assert b"openapi" in response.content
