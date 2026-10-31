"""Student self sign-up (public). Creates the account, signs the student in, and leaves the
academic record flagged as self-declared until the placement cell confirms it."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts import services as auth_services
from apps.accounts.cookies import set_auth_cookies
from apps.accounts.portals import Portal
from apps.core.csrf import enforce_csrf
from apps.core.models import Institution
from apps.core.services import record_audit
from apps.students import services as student_services
from apps.students.models import Department
from apps.students.validators import validate_registration_number

from .serializers import MeSerializer
from .views import _PublicAuthView


class SignupSerializer(serializers.Serializer):
    institution_code = serializers.SlugField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, allow_blank=True, default="")
    roll_number = serializers.CharField(max_length=8, validators=[validate_registration_number])
    department_id = serializers.IntegerField()
    graduation_year = serializers.IntegerField(min_value=2000, max_value=2100)
    cgpa = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10)
    active_backlogs = serializers.IntegerField(min_value=0, max_value=50, default=0)


class SignupDepartmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class SignupOptionSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    email_domain = serializers.CharField(allow_blank=True)
    departments = SignupDepartmentSerializer(many=True)


class SignupOptionsView(_PublicAuthView):
    """Institutions that accept self sign-up, with their departments."""

    @extend_schema(responses=SignupOptionSerializer(many=True))
    def get(self, request):
        rows = []
        for inst in Institution.objects.filter(is_active=True, allow_student_signup=True).order_by("name"):
            rows.append(
                {
                    "code": inst.code,
                    "name": inst.name,
                    "email_domain": inst.student_email_domain,
                    "departments": list(Department.objects.filter(institution=inst).values("id", "code", "name")),
                }
            )
        return Response(rows)


class SignupView(_PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"

    @extend_schema(request=SignupSerializer, responses={201: MeSerializer})
    def post(self, request):
        enforce_csrf(request._request)
        data = SignupSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        institution = Institution.objects.filter(code=v.pop("institution_code"), is_active=True).first()
        department = (
            Department.objects.filter(pk=v.pop("department_id"), institution=institution).first()
            if institution
            else None
        )
        if institution is None or department is None:
            return Response({"detail": "Choose your institution and department."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            student = student_services.self_signup(institution=institution, department=department, **v)
        except student_services.StudentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        user = student.user
        record_audit(actor=user, action="auth.signup", target=user, request=request)
        response = Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)
        set_auth_cookies(response, auth_services.issue_tokens(user, Portal.INTERNAL), Portal.INTERNAL)
        return response
