import hashlib
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.services import record_audit

from . import totp
from .models import TOTPDevice
from .portals import Portal
from .roles import Role, has_role, user_roles


class LoginLocked(Exception):
    pass


class LoginFailed(Exception):
    pass


class MFARequired(Exception):  # noqa: N818 - a control-flow signal, not an error
    def __init__(self, challenge):
        super().__init__("Two-factor code required.")
        self.challenge = challenge


class MFAError(ValueError):
    pass


MFA_CHALLENGE_SALT = "accounts.mfa-challenge"
MFA_CHALLENGE_SECONDS = 300


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str


def _lockout_key(email):
    # Hash so the cache never holds an email address.
    return "login-fail:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()


def is_locked_out(email):
    return cache.get(_lockout_key(email), 0) >= settings.LOGIN_LOCKOUT_THRESHOLD


def _record_failure(email):
    key = _lockout_key(email)
    cache.add(key, 0, timeout=settings.LOGIN_LOCKOUT_SECONDS)
    cache.incr(key)


def can_use_portal(user, portal):
    """Recruiters use only the recruiter portal; everyone else only the internal one."""
    is_recruiter = has_role(user, Role.RECRUITER)
    return is_recruiter if portal == Portal.RECRUITER else not is_recruiter


def mfa_device(user):
    return TOTPDevice.objects.filter(user=user, confirmed_at__isnull=False).first()


def mfa_setup_required(user):
    """Privileged roles must enrol an authenticator (CES §1.1: TOTP MFA for admin roles)."""
    required = set(getattr(settings, "MFA_REQUIRED_ROLES", ()))
    return bool(required & user_roles(user)) and mfa_device(user) is None


def issue_tokens(user, portal):
    refresh = RefreshToken.for_user(user)
    refresh["portal"] = str(portal)
    if mfa_setup_required(user):
        # Restricted session: only /auth/* works until an authenticator is confirmed.
        refresh["mfa_setup"] = True
    return TokenPair(access=str(refresh.access_token), refresh=str(refresh))


def login(*, email, password, portal, request=None):
    """Authenticate and issue a portal-bound token pair.

    Every failure, including an unknown email or a wrong portal, counts toward the lockout
    and returns the same error, so the response does not reveal whether an account exists.
    """
    if is_locked_out(email):
        raise LoginLocked
    user = authenticate(request, email=email, password=password)
    if user is None or not can_use_portal(user, portal):
        _record_failure(email)
        raise LoginFailed
    if mfa_device(user) is not None:
        challenge = signing.dumps({"uid": user.pk, "portal": str(portal)}, salt=MFA_CHALLENGE_SALT)
        raise MFARequired(challenge)
    cache.delete(_lockout_key(email))
    record_audit(actor=user, action=f"auth.login.{portal}", target=user, request=request)
    return user, issue_tokens(user, portal)


def complete_mfa_login(*, challenge, code, portal, request=None):
    """Second step of login: a valid, unexpired challenge plus a fresh TOTP code."""
    try:
        data = signing.loads(challenge or "", salt=MFA_CHALLENGE_SALT, max_age=MFA_CHALLENGE_SECONDS)
    except signing.BadSignature as exc:
        raise LoginFailed from exc
    if data.get("portal") != str(portal):
        raise LoginFailed
    user = get_user_model().objects.filter(pk=data["uid"], is_active=True).first()
    if user is None:
        raise LoginFailed
    if is_locked_out(user.email):
        raise LoginLocked
    device = mfa_device(user)
    counter = device and totp.verify(device.secret, code, last_counter=device.last_counter)
    if not counter:
        _record_failure(user.email)
        raise LoginFailed
    device.last_counter = counter
    device.save(update_fields=["last_counter"])
    cache.delete(_lockout_key(user.email))
    record_audit(actor=user, action=f"auth.login.{portal}.mfa", target=user, request=request)
    return user, issue_tokens(user, portal)


def start_mfa_setup(user):
    """Create (or replace an unconfirmed) authenticator secret. A confirmed device must be
    disabled first, so an attacker with a session cannot silently swap it."""
    device = TOTPDevice.objects.filter(user=user).first()
    if device is not None and device.is_confirmed:
        raise MFAError("Two-factor authentication is already enabled.")
    secret = totp.new_secret()
    TOTPDevice.objects.update_or_create(
        user=user, defaults={"secret": secret, "confirmed_at": None, "last_counter": None}
    )
    return secret, totp.provisioning_uri(secret, user.email)


def confirm_mfa(user, code, request=None):
    device = TOTPDevice.objects.filter(user=user, confirmed_at__isnull=True).first()
    if device is None:
        raise MFAError("Start the set-up first.")
    counter = totp.verify(device.secret, code)
    if not counter:
        raise MFAError("That code is not valid. Check your authenticator's clock and try again.")
    device.confirmed_at = timezone.now()
    device.last_counter = counter
    device.save(update_fields=["confirmed_at", "last_counter"])
    record_audit(actor=user, action="auth.mfa.enable", target=user, request=request)
    return device


def disable_mfa(user, code, request=None):
    device = mfa_device(user)
    if device is None:
        raise MFAError("Two-factor authentication is not enabled.")
    if set(getattr(settings, "MFA_REQUIRED_ROLES", ())) & user_roles(user):
        raise MFAError("Your role requires two-factor authentication.")
    if not totp.verify(device.secret, code, last_counter=device.last_counter):
        raise MFAError("That code is not valid.")
    device.delete()
    record_audit(actor=user, action="auth.mfa.disable", target=user, request=request)


def rotate_refresh(raw_refresh, portal):
    """Exchange a refresh token for a new pair; the old refresh token is blacklisted."""
    refresh = RefreshToken(raw_refresh)  # raises TokenError if invalid, expired or blacklisted
    if refresh.get("portal") != portal:
        raise TokenError("Token is not valid for this portal.")
    user = get_user_model().objects.filter(pk=refresh["user_id"], is_active=True).first()
    if user is None or not can_use_portal(user, portal):
        raise TokenError("User is no longer allowed to use this portal.")
    refresh.blacklist()
    return user, issue_tokens(user, portal)


def logout(raw_refresh, *, user=None, request=None):
    """Blacklist the refresh token if it is still valid. Always succeeds."""
    if raw_refresh:
        try:
            RefreshToken(raw_refresh).blacklist()
        except TokenError:
            pass
    if user is not None and user.is_authenticated:
        record_audit(actor=user, action="auth.logout", target=user, request=request)
