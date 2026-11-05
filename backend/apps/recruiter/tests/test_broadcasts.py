"""Recruiter broadcasts reach only the scoped candidates of the recruiter's approved drive."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.drives.models import Registration, RegistrationStatus
from apps.notifications.models import Notification
from apps.recruiter import services
from apps.recruiter.models import AccessAction, AccessLog, RecruiterBroadcast

from .test_recruiter_security import recruiter_client

pytestmark = pytest.mark.django_db


def url(drive):
    return f"/api/v1/recruiter/drives/{drive.pk}/broadcasts/"


@pytest.fixture
def send(django_capture_on_commit_callbacks):
    """POST a broadcast and run the on-commit delivery inside the test transaction."""

    def _send(client, drive, **extra):
        with django_capture_on_commit_callbacks(execute=True):
            return client.post(
                url(drive), {"title": "Pre-placement talk", "body": "Join at 10 AM.", **extra}, format="json"
            )

    return _send


def test_broadcast_reaches_only_registered_students_of_the_granted_drive(world, send):
    client = recruiter_client(world["recruiter_a"])
    response = send(client, world["drive_a"])
    assert response.status_code == 201, response.content
    assert response.json()["recipient_count"] == 1
    recipients = set(Notification.objects.filter(kind="recruiter_broadcast").values_list("recipient_id", flat=True))
    assert recipients == {world["in_a"].user_id}
    note = Notification.objects.get(kind="recruiter_broadcast")
    assert note.title.startswith("Alpha — Backend Engineer:") and note.link == f"/student/drives/{world['drive_a'].pk}"
    log = AccessLog.objects.get(action=AccessAction.BROADCAST)
    assert log.student_ids == [world["in_a"].pk]


def test_recruiter_cannot_broadcast_to_another_drive(world, send):
    client = recruiter_client(world["recruiter_a"])
    assert send(client, world["drive_b"]).status_code == 404
    assert not Notification.objects.filter(kind="recruiter_broadcast").exists()
    assert AccessLog.objects.filter(action=AccessAction.DENIED, drive_id_requested=world["drive_b"].pk).exists()


def test_expired_or_revoked_grant_cannot_broadcast(world, head, send):
    grant = world["grant_a"]
    grant.expires_at = timezone.now() - timedelta(minutes=1)
    grant.starts_at = timezone.now() - timedelta(days=1)
    grant.save()
    assert send(recruiter_client(world["recruiter_a"]), world["drive_a"]).status_code == 404

    grant.expires_at = timezone.now() + timedelta(days=1)
    grant.save()
    services.revoke_grant(grant, actor=head)
    assert send(recruiter_client(world["recruiter_a"]), world["drive_a"]).status_code == 404
    assert not RecruiterBroadcast.objects.exists()


def test_shortlisted_audience(world, make_student, send):
    from apps.drives import services as drive_services

    second = make_student(name="Second")
    drive_services.register(world["drive_a"], second)
    Registration.objects.filter(drive=world["drive_a"], student=second).update(status=RegistrationStatus.SHORTLISTED)
    client = recruiter_client(world["recruiter_a"])
    response = send(client, world["drive_a"], audience="shortlisted")
    assert response.json()["recipient_count"] == 1
    assert set(Notification.objects.filter(kind="recruiter_broadcast").values_list("recipient_id", flat=True)) == {
        second.user_id
    }


@override_settings(RECRUITER_BROADCASTS_PER_DAY=2)
def test_broadcasts_are_capped_per_day(world, send):
    client = recruiter_client(world["recruiter_a"])
    assert send(client, world["drive_a"]).status_code == 201
    assert send(client, world["drive_a"]).status_code == 201
    assert send(client, world["drive_a"]).status_code == 400


def test_internal_portal_token_cannot_broadcast(world, as_user, send):
    assert send(as_user(world["recruiter_a"]), world["drive_a"]).status_code in (401, 403)


def test_head_reviews_broadcasts_and_officer_cannot(world, head, officer, as_user, send):
    send(recruiter_client(world["recruiter_a"]), world["drive_a"])
    rows = as_user(head).get("/api/v1/recruiter-admin/broadcasts/").json()["results"]
    assert rows[0]["recipient_count"] == 1 and rows[0]["recruiter_email"] == "rec-a@alpha.example"
    assert as_user(officer).get("/api/v1/recruiter-admin/broadcasts/").status_code == 403
    # Recruiter sees their own broadcast history, without recipient identities.
    history = recruiter_client(world["recruiter_a"]).get(url(world["drive_a"])).json()
    assert history[0]["recipient_count"] == 1 and "student_ids" not in history[0]
