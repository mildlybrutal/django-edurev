from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role, has_role
from apps.core.services import client_ip, record_audit
from apps.drives.models import ACTIVE_REGISTRATION, Registration, RegistrationStatus
from apps.students.models import StudentProfile

from .models import (
    RELEASABLE_FIELDS,
    AccessAction,
    AccessLog,
    BroadcastAudience,
    CandidateScope,
    GrantStatus,
    RecruiterAccessGrant,
    RecruiterBroadcast,
)


class GrantError(ValueError):
    pass


@transaction.atomic
def create_recruiter(*, institution, email, first_name, last_name, password, created_by, request=None):
    User = get_user_model()
    if User.objects.filter(email__iexact=email).exists():
        raise GrantError("An account with this email already exists.")
    user = User.objects.create_user(
        email=email, password=password, first_name=first_name, last_name=last_name, institution=institution
    )
    user.groups.add(Group.objects.get(name=Role.RECRUITER))
    record_audit(actor=created_by, action="recruiter.create", target=user, request=request)
    return user


def _validate_fields(fields):
    unknown = set(fields) - set(RELEASABLE_FIELDS)
    if unknown:
        raise GrantError(f"Fields cannot be released: {', '.join(sorted(unknown))}.")
    if not fields:
        raise GrantError("Release at least one field.")
    return sorted(set(fields))


@transaction.atomic
def create_grant(
    *,
    recruiter,
    drive,
    allowed_fields,
    expires_at,
    granted_by,
    candidate_scope=CandidateScope.REGISTERED,
    starts_at=None,
    request=None,
):
    if not has_role(recruiter, Role.RECRUITER):
        raise GrantError("Grants can only be issued to recruiter accounts.")
    if recruiter.institution_id != drive.institution_id or granted_by.institution_id != drive.institution_id:
        raise GrantError("Recruiter and drive must belong to your institution.")
    starts_at = starts_at or timezone.now()
    if expires_at <= starts_at:
        raise GrantError("Expiry must be after the start.")
    grant = RecruiterAccessGrant.objects.create(
        institution_id=drive.institution_id,
        recruiter=recruiter,
        drive=drive,
        allowed_fields=_validate_fields(allowed_fields),
        candidate_scope=candidate_scope,
        starts_at=starts_at,
        expires_at=expires_at,
        granted_by=granted_by,
    )
    record_audit(
        actor=granted_by,
        action="recruiter.grant.create",
        target=grant,
        request=request,
        after={"drive": drive.pk, "fields": grant.allowed_fields, "expires_at": expires_at.isoformat()},
    )
    return grant


def update_grant(grant, *, actor, request=None, allowed_fields=None, expires_at=None, candidate_scope=None):
    before = {
        "fields": grant.allowed_fields,
        "expires_at": grant.expires_at.isoformat(),
        "scope": grant.candidate_scope,
    }
    if allowed_fields is not None:
        grant.allowed_fields = _validate_fields(allowed_fields)
    if expires_at is not None:
        if expires_at <= grant.starts_at:
            raise GrantError("Expiry must be after the start.")
        grant.expires_at = expires_at
    if candidate_scope is not None:
        grant.candidate_scope = candidate_scope
    grant.save()
    record_audit(
        actor=actor,
        action="recruiter.grant.update",
        target=grant,
        request=request,
        before=before,
        after={
            "fields": grant.allowed_fields,
            "expires_at": grant.expires_at.isoformat(),
            "scope": grant.candidate_scope,
        },
    )
    return grant


def revoke_grant(grant, *, actor, request=None):
    grant.status = GrantStatus.REVOKED
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["status", "revoked_at", "updated_at"])
    record_audit(actor=actor, action="recruiter.grant.revoke", target=grant, request=request)
    return grant


def valid_grant(recruiter, drive_id, now=None):
    """The recruiter's currently valid grant for a drive, or None. Checked on every request."""
    now = now or timezone.now()
    return (
        RecruiterAccessGrant.objects.select_related("drive__company")
        .filter(
            recruiter=recruiter,
            drive_id=drive_id,
            status=GrantStatus.ACTIVE,
            starts_at__lte=now,
            expires_at__gt=now,
            institution_id=recruiter.institution_id,
        )
        .order_by("-expires_at")
        .first()
    )


def valid_grants(recruiter, now=None):
    now = now or timezone.now()
    return RecruiterAccessGrant.objects.select_related("drive__company").filter(
        recruiter=recruiter,
        status=GrantStatus.ACTIVE,
        starts_at__lte=now,
        expires_at__gt=now,
        institution_id=recruiter.institution_id,
    )


def scoped_candidates(grant):
    """Layer 1: only students registered (or shortlisted, per grant scope) for the granted drive.
    Applied before any search, filter or lookup."""
    statuses = (
        [RegistrationStatus.SHORTLISTED, RegistrationStatus.SELECTED, RegistrationStatus.NOT_SELECTED]
        if grant.candidate_scope == CandidateScope.SHORTLISTED
        else list(ACTIVE_REGISTRATION)
    )
    registered = Registration.objects.filter(drive_id=grant.drive_id, status__in=statuses).values("student_id")
    return StudentProfile.objects.filter(institution_id=grant.institution_id, pk__in=registered).select_related(
        "user", "department"
    )


def log_access(*, recruiter, grant, action, request, student_ids=(), fields=(), drive_id=None, query=None):
    return AccessLog.objects.create(
        institution_id=recruiter.institution_id,
        recruiter=recruiter,
        grant=grant,
        drive_id_requested=drive_id,
        action=action,
        path=request.path[:300],
        query=query or {},
        student_ids=list(student_ids),
        fields_released=list(fields),
        ip=client_ip(request),
    )


class BroadcastError(ValueError):
    pass


SHORTLIST_STATUSES = (RegistrationStatus.SHORTLISTED, RegistrationStatus.SELECTED, RegistrationStatus.NOT_SELECTED)


def broadcast_recipients(grant, audience):
    """Always a subset of the grant's scoped candidates (Layer 1), so a broadcast can never reach
    a student outside the recruiter's approved drive."""
    qs = scoped_candidates(grant)
    if audience == BroadcastAudience.SHORTLISTED:
        shortlisted = Registration.objects.filter(drive_id=grant.drive_id, status__in=SHORTLIST_STATUSES)
        qs = qs.filter(pk__in=shortlisted.values("student_id"))
    return qs


def create_broadcast(*, grant, audience, title, body, request):
    from datetime import timedelta

    from django.conf import settings

    title, body = title.strip(), body.strip()
    if not title or not body:
        raise BroadcastError("Add a subject and a message.")
    limit = getattr(settings, "RECRUITER_BROADCASTS_PER_DAY", 5)
    since = timezone.now() - timedelta(days=1)
    if (
        RecruiterBroadcast.objects.filter(
            grant__recruiter=grant.recruiter, drive_id=grant.drive_id, created_at__gte=since
        ).count()
        >= limit
    ):
        raise BroadcastError(f"You can send at most {limit} broadcasts per drive in 24 hours.")
    recipients = list(broadcast_recipients(grant, audience).values_list("pk", flat=True))
    if not recipients:
        raise BroadcastError("No candidates match this audience yet.")
    broadcast = RecruiterBroadcast.objects.create(
        institution_id=grant.institution_id,
        grant=grant,
        recruiter=grant.recruiter,
        drive_id=grant.drive_id,
        audience=audience,
        title=title,
        body=body,
        recipient_count=len(recipients),
    )
    log_access(
        recruiter=grant.recruiter,
        grant=grant,
        action=AccessAction.BROADCAST,
        request=request,
        student_ids=recipients,
        drive_id=grant.drive_id,
        query={"broadcast": broadcast.pk, "audience": audience},
    )
    from .tasks import deliver_broadcast

    transaction.on_commit(lambda: deliver_broadcast.delay(broadcast.pk))
    return broadcast


def deliver_broadcast(broadcast_id):
    """Fan the broadcast out as notifications. Recipients are re-resolved at delivery time and the
    grant is re-checked, so a grant revoked before delivery sends nothing."""
    from apps.notifications.services import notify

    broadcast = RecruiterBroadcast.objects.select_related("grant", "drive__company").get(pk=broadcast_id)
    if broadcast.sent_at is not None or not broadcast.grant.is_valid():
        return 0
    drive = broadcast.drive
    sent = 0
    for student in broadcast_recipients(broadcast.grant, broadcast.audience).select_related("user"):
        notify(
            student.user,
            kind="recruiter_broadcast",
            title=f"{drive.company.name} — {drive.role_title}: {broadcast.title}",
            body=broadcast.body,
            link=f"/student/drives/{drive.pk}",
        )
        sent += 1
    broadcast.recipient_count = sent
    broadcast.sent_at = timezone.now()
    broadcast.save(update_fields=["recipient_count", "sent_at", "updated_at"])
    return sent
