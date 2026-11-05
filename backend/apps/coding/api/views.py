from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.coding import services
from apps.coding.models import CodingProfile
from apps.students.api.views import resolve_student
from apps.students.selectors import student_for_user


class CodingProfileSerializer(serializers.ModelSerializer):
    platform_label = serializers.CharField(source="get_platform_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    score = serializers.FloatField(allow_null=True)
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = CodingProfile
        fields = [
            "id",
            "platform",
            "platform_label",
            "username",
            "status",
            "status_label",
            "score",
            "stats",
            "explanation",
            "error",
            "last_synced_at",
            "verification_status",
        ]

    def get_verification_status(self, obj) -> str | None:
        return obj.evidence.verification_status if obj.evidence_id and obj.evidence else None


class CodingInput(serializers.Serializer):
    github_username = serializers.CharField(required=False, allow_blank=True, max_length=60)
    leetcode_username = serializers.CharField(required=False, allow_blank=True, max_length=60)
    codeforces_username = serializers.CharField(required=False, allow_blank=True, max_length=60)


def _payload(student):
    score, profiles = services.coding_activity([student.pk]).get(student.pk, (None, []))
    return {
        "coding_activity": score,
        "profiles": CodingProfileSerializer(sorted(profiles, key=lambda p: p.platform), many=True).data,
        "note": "Public activity is supporting evidence, not proof of expertise. LeetCode figures come from an "
        "unofficial public source.",
    }


class CodingView(APIView):
    """GET /students/:id/coding — ratings for a visible student. POST (self) — set usernames."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, student_id):
        return Response(_payload(resolve_student(request, student_id)))

    @extend_schema(request=CodingInput, responses=OpenApiTypes.OBJECT)
    def post(self, request, student_id):
        student = resolve_student(request, student_id)
        if student.user_id != request.user.pk:
            raise PermissionDenied("Students set their own coding profiles.")
        data = CodingInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.set_profiles(
                student,
                github=data.validated_data.get("github_username"),
                leetcode=data.validated_data.get("leetcode_username"),
                codeforces=data.validated_data.get("codeforces_username"),
            )
        except services.CodingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_payload(student))


class CodingRefreshView(APIView):
    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        student = student_for_user(request.user)
        if student is None:
            raise PermissionDenied("Only students refresh their own coding profiles.")
        queued = services.request_refresh(student)
        body = _payload(student)
        body["queued"] = len(queued)
        return Response(body, status=status.HTTP_202_ACCEPTED)
