from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role, has_role
from apps.core.services import client_ip, record_audit
from apps.drives.models import ACTIVE_REGISTRATION, Registration, RegistrationStatus
from apps.students.models import StudentProfile

from .models import RELEASABLE_FIELDS, AccessLog, CandidateScope, GrantStatus, RecruiterAccessGrant


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
