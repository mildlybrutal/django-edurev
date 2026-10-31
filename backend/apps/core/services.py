from .models import AuditLog


def client_ip(request):
    """Client address as seen by Django. Proxy-header trust is configured at deployment."""
    return request.META.get("REMOTE_ADDR") if request is not None else None


def record_audit(*, actor, action, target=None, before=None, after=None, request=None, institution=None):
    """Append an audit entry for a privileged action."""
    if institution is None and actor is not None:
        institution = getattr(actor, "institution", None)
    return AuditLog.objects.create(
        institution=institution,
        actor=actor if actor is not None and actor.is_authenticated else None,
        action=action,
        target_type=target._meta.label if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        before=before,
        after=after,
        ip=client_ip(request),
    )
