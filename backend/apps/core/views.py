import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

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
