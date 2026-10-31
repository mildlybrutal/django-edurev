from rest_framework.permissions import BasePermission

from .roles import has_role


class HasAnyRole(BasePermission):
    """Grants access when the user holds at least one of `roles`. Build with `roles_required`."""

    roles = ()

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and has_role(request.user, *self.roles))


def roles_required(*roles):
    name = "HasRole_" + "_".join(str(r) for r in roles)
    return type(name, (HasAnyRole,), {"roles": roles})


class SameInstitution(BasePermission):
    """Object-level check: the object belongs to the requesting user's institution."""

    def has_object_permission(self, request, view, obj):
        return obj.institution_id is not None and obj.institution_id == request.user.institution_id
