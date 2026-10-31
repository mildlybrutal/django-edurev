"""Notification service. Every notification is stored in-app; additional channels (email now,
SMS later) are pluggable and chosen per kind via settings.NOTIFICATION_EMAIL_KINDS."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)


class InAppChannel:
    def send(self, notification):
        return None  # Stored row is the in-app notification.


class EmailChannel:
    def send(self, notification):
        if notification.kind not in getattr(settings, "NOTIFICATION_EMAIL_KINDS", ()):
            return
        try:
            send_mail(
                notification.title,
                notification.body or notification.title,
                None,
                [notification.recipient.email],
                fail_silently=False,
            )
        except Exception:
            # Never let a mail outage break the business action; the in-app copy exists.
            logger.exception("notification email failed", extra={"notification_id": notification.pk})


CHANNELS = [InAppChannel(), EmailChannel()]


def notify(recipient, *, kind, title, body="", link=""):
    notification = Notification.objects.create(
        institution_id=getattr(recipient, "institution_id", None),
        recipient=recipient,
        kind=kind,
        title=title[:200],
        body=body,
        link=link,
    )
    for channel in CHANNELS:
        channel.send(notification)
    return notification


def mark_read(recipient, ids=None):
    qs = Notification.objects.filter(recipient=recipient, read_at__isnull=True)
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    return qs.update(read_at=timezone.now())
