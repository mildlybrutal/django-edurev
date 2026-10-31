from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.core.csrf import enforce_csrf

from .portals import Portal

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
MFA_SETUP_ALLOWED_PREFIXES = ("/api/v1/auth/", "/api/v1/recruiter/auth/", "/api/v1/recruiter/me/")


class MFASetupRequired(PermissionDenied):
    default_detail = "Set up two-factor authentication to continue."
    default_code = "mfa_setup_required"


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the access token from an httpOnly cookie and enforces CSRF on unsafe methods.

    Each portal has its own cookie and its own `portal` token claim, so an internal token is
    useless on recruiter endpoints and vice versa (P06 §16: no shared session or throttle scope).
    """

    portal = Portal.INTERNAL

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIES[self.portal]["access"])
        if raw_token is None:
            return None
        validated = self.get_validated_token(raw_token)
        if validated.get("portal") != self.portal:
            raise InvalidToken("Token is not valid for this portal.")
        user = self.get_user(validated)
        if validated.get("mfa_setup") and not request.path.startswith(MFA_SETUP_ALLOWED_PREFIXES):
            raise MFASetupRequired()
        if request.method not in SAFE_METHODS:
            enforce_csrf(request._request)
        return user, validated

    def authenticate_header(self, request):
        return 'Cookie realm="api"'


class RecruiterCookieJWTAuthentication(CookieJWTAuthentication):
    portal = Portal.RECRUITER
