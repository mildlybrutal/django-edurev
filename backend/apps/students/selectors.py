from apps.accounts.roles import Role, has_role

from .models import StudentProfile


def student_for_user(user):
    """The student record of a signed-in student, or None."""
    if not user.is_authenticated:
        return None
    return StudentProfile.objects.select_related("department", "user").filter(user=user).first()


def visible_students(user):
    """Students a staff user may see: officers/heads/admins see the whole institution,
    faculty see their mentees, students see only themselves. Always institution-scoped."""
    qs = StudentProfile.objects.select_related("department", "user", "mentor").filter(
        institution_id=user.institution_id
    )
    if has_role(user, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN):
        return qs
    if has_role(user, Role.FACULTY):
        return qs.filter(mentor=user)
    if has_role(user, Role.STUDENT):
        return qs.filter(user=user)
    return qs.none()


def can_view_student(user, student):
    return visible_students(user).filter(pk=student.pk).exists()
