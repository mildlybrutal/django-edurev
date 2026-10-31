from rest_framework.exceptions import NotFound, ValidationError


class InstitutionScopedMixin:
    """Restricts a view's queryset to the requesting user's institution.

    This is the queryset half of "enforced twice" (CES §1.1): objects from another
    institution are invisible (404), not merely forbidden.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        institution_id = getattr(self.request.user, "institution_id", None)
        if institution_id is None:
            return qs.none()
        return qs.filter(institution_id=institution_id)


def service_call(fn, *args, error_types=(ValueError,), **kwargs):
    """Run a service function and turn its domain errors into a 400 response."""
    try:
        return fn(*args, **kwargs)
    except error_types as exc:
        raise ValidationError({"detail": str(exc)}) from exc


def get_scoped_or_404(queryset, institution_id, **lookup):
    obj = queryset.filter(institution_id=institution_id, **lookup).first()
    if obj is None:
        raise NotFound()
    return obj
