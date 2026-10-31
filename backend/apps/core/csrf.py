from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    """Apply Django's CSRF check to a DRF request (cookie auth needs it; DRF views are csrf_exempt)."""
    check = _CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF failed: {reason}")
