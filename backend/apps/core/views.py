import logging

from django.core import signing
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    """Liveness: the process is up. Touches no dependencies."""
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request):
    """Readiness: the database and cache are reachable."""
    checks = {"database": _check_database(), "cache": _check_cache()}
    ok = all(checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status=200 if ok else 503,
    )


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        logger.exception("readiness: database check failed")
        return False


def _check_cache():
    try:
        cache.set("ready-probe", "1", timeout=5)
        return cache.get("ready-probe") == "1"
    except Exception:
        logger.exception("readiness: cache check failed")
        return False


class StoredFileView(APIView):
    """GET /api/v1/files/<token>/ — serve a file from database storage (ADR 0011).

    The signed, expiring token is the authorization, exactly like an S3 pre-signed URL: the
    permission check and the audit entry happen in the endpoint that issued the link. Responses
    are sandboxed so an uploaded file can never run script on the app's origin, and may be framed
    only by the app itself (the in-app resume/certificate viewer is an iframe)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "file_link"

    @extend_schema(exclude=True)
    def get(self, request, token):
        from apps.core.file_storage import LinkExpired, read_link
        from apps.core.models import StoredFile

        try:
            name, content_type = read_link(token)
        except LinkExpired:
            return JsonResponse({"detail": "This link has expired. Open the file again."}, status=403)
        except signing.BadSignature:
            return JsonResponse({"detail": "Invalid link."}, status=403)
        row = StoredFile.objects.filter(name=name).only("content").first()
        if row is None:
            return JsonResponse({"detail": "Not found."}, status=404)
        response = HttpResponse(bytes(row.content), content_type=content_type)
        response["Content-Disposition"] = "inline"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "sandbox"
        response["Cache-Control"] = "private, no-store"
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response
