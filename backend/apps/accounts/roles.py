from django.db import models


class Role(models.TextChoices):
    """Each role is a Django group of the same name, created by migration 0002."""

    STUDENT = "student", "Student"
    FACULTY = "faculty", "Faculty"
    PLACEMENT_OFFICER = "placement_officer", "Placement Officer"
    PLACEMENT_HEAD = "placement_head", "Placement Head"
    RECRUITER = "recruiter", "Recruiter"
    ADMIN = "admin", "Administrator"


def user_roles(user):
    if not user.is_authenticated:
        return set()
    return set(user.groups.filter(name__in=Role.values).values_list("name", flat=True))


def has_role(user, *roles):
    return bool(user_roles(user) & {str(r) for r in roles})
