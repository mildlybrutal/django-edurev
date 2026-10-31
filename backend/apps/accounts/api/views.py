from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts import services
from apps.accounts.authentication import CookieJWTAuthentication, RecruiterCookieJWTAuthentication
from apps.accounts.cookies import clear_auth_cookies, set_auth_cookies
from apps.accounts.portals import Portal
from apps.core.csrf import enforce_csrf

from .serializers import LoginResultSerializer, LoginSerializer, MeSerializer, MFACodeSerializer, MFASetupSerializer


class _PublicAuthView(APIView):
    """Auth endpoints run before a user is known; CSRF is still enforced explicitly."""

    authentication_classes = []
    permission_classes = [AllowAny]
    portal = Portal.INTERNAL


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(_PublicAuthView):
    @extend_schema(responses={204: None})
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginView(_PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=LoginResultSerializer)
    def post(self, request):
        enforce_csrf(request._request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, tokens = services.login(**serializer.validated_data, portal=self.portal, request=request)
        except services.MFARequired as challenge:
            # Password accepted; the session is only issued after the TOTP step.
            response = Response({"mfa_required": True})
            response.set_cookie(
                settings.AUTH_COOKIES[self.portal]["mfa"],
                challenge.challenge,
                max_age=services.MFA_CHALLENGE_SECONDS,
                path=settings.AUTH_COOKIES[self.portal]["refresh_path"],
                domain=settings.AUTH_COOKIE_DOMAIN,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=True,
                samesite=settings.AUTH_COOKIE_SAMESITE,
            )
            return response
        except services.LoginLocked:
            return Response(
                {"detail": "Too many failed attempts. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except services.LoginFailed:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        response = Response(MeSerializer(user).data)
        set_auth_cookies(response, tokens, self.portal)
        return response


class MFAVerifyView(_PublicAuthView):
    """Second login step: TOTP code + the challenge cookie set by the password step."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=MFACodeSerializer, responses=MeSerializer)
    def post(self, request):
        enforce_csrf(request._request)
        data = MFACodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        cookie = settings.AUTH_COOKIES[self.portal]["mfa"]
        try:
            user, tokens = services.complete_mfa_login(
                challenge=request.COOKIES.get(cookie),
                code=data.validated_data["code"],
                portal=self.portal,
                request=request,
            )
        except services.LoginLocked:
            return Response(
                {"detail": "Too many failed attempts. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except services.LoginFailed:
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_401_UNAUTHORIZED)
        response = Response(MeSerializer(user).data)
        set_auth_cookies(response, tokens, self.portal)
        response.delete_cookie(
            cookie,
            path=settings.AUTH_COOKIES[self.portal]["refresh_path"],
            domain=settings.AUTH_COOKIE_DOMAIN,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
        return response


class MFASetupView(APIView):
    """Signed-in user: create an authenticator secret (shown once) to add to an authenticator app."""

    permission_classes = [IsAuthenticated]
    portal = Portal.INTERNAL

    @extend_schema(request=None, responses=MFASetupSerializer)
    def post(self, request):
        try:
            secret, uri = services.start_mfa_setup(request.user)
        except services.MFAError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response = Response({"secret": secret, "otpauth_uri": uri})
        response["Cache-Control"] = "no-store"
        return response


class MFAConfirmView(APIView):
    permission_classes = [IsAuthenticated]
    portal = Portal.INTERNAL

    @extend_schema(request=MFACodeSerializer, responses=MeSerializer)
    def post(self, request):
        data = MFACodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.confirm_mfa(request.user, data.validated_data["code"], request=request)
        except services.MFAError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Replace a restricted (set-up pending) session with a full one.
        response = Response(MeSerializer(request.user).data)
        set_auth_cookies(response, services.issue_tokens(request.user, self.portal), self.portal)
        return response


class MFADisableView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=MFACodeSerializer, responses=MeSerializer)
    def post(self, request):
        data = MFACodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.disable_mfa(request.user, data.validated_data["code"], request=request)
        except services.MFAError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MeSerializer(request.user).data)


class RefreshView(_PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        enforce_csrf(request._request)
        raw = request.COOKIES.get(settings.AUTH_COOKIES[self.portal]["refresh"])
        if not raw:
            return Response({"detail": "Not authenticated."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            _, tokens = services.rotate_refresh(raw, self.portal)
        except TokenError:
            response = Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
            clear_auth_cookies(response, self.portal)
            return response
        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, tokens, self.portal)
        return response


class LogoutView(_PublicAuthView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        enforce_csrf(request._request)
        raw = request.COOKIES.get(settings.AUTH_COOKIES[self.portal]["refresh"])
        user = self._optional_user(request)
        services.logout(raw, user=user, request=request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response, self.portal)
        return response

    def _optional_user(self, request):
        auth_class = RecruiterCookieJWTAuthentication if self.portal == Portal.RECRUITER else CookieJWTAuthentication
        try:
            result = auth_class().authenticate(request)
        except Exception:
            return None
        return result[0] if result else None


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)
