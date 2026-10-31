from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.api import service_call
from apps.evidence import services
from apps.evidence.models import EvidenceItem, EvidenceSkillTag, SourceType
from apps.students.selectors import student_for_user, visible_students
from apps.taxonomy.models import POSITIVE_LEVEL_CHOICES, Level, Skill
from apps.verification.models import Verification
from apps.verification.services import notify_verification_requested


class TagSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(source="skill.name", read_only=True)
    skill_id = serializers.IntegerField()
    level_label = serializers.SerializerMethodField()

    class Meta:
        model = EvidenceSkillTag
        fields = ["skill_id", "skill", "claimed_level", "level_label"]

    def get_level_label(self, obj) -> str:
        return Level(obj.claimed_level).label


class VerificationSerializer(serializers.ModelSerializer):
    reviewer = serializers.SerializerMethodField()

    class Meta:
        model = Verification
        fields = ["id", "decision", "comment", "created_at", "reviewer"]

    def get_reviewer(self, obj) -> str:
        return obj.reviewer.get_full_name() or obj.reviewer.email


class EvidenceSerializer(serializers.ModelSerializer):
    skill_tags = TagSerializer(many=True, read_only=True)
    verifications = VerificationSerializer(many=True, read_only=True)
    source_label = serializers.CharField(source="get_source_type_display", read_only=True)
    status_label = serializers.CharField(source="get_verification_status_display", read_only=True)
    student_id = serializers.IntegerField(read_only=True)
    student_name = serializers.CharField(source="student.name", read_only=True)
    is_institutional = serializers.SerializerMethodField()

    class Meta:
        model = EvidenceItem
        fields = [
            "id",
            "student_id",
            "student_name",
            "source_type",
            "source_label",
            "title",
            "description",
            "source_url",
            "external_reference",
            "extracted_data",
            "submitted_at",
            "verification_status",
            "status_label",
            "is_institutional",
            "skill_tags",
            "verifications",
        ]

    def get_is_institutional(self, obj) -> bool:
        from apps.evidence.models import INSTITUTIONAL_SOURCES

        return obj.source_type in INSTITUTIONAL_SOURCES


class TagInputSerializer(serializers.Serializer):
    skill_id = serializers.IntegerField()
    claimed_level = serializers.ChoiceField(choices=POSITIVE_LEVEL_CHOICES)


class EvidenceWriteSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=SourceType.choices)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    source_url = serializers.URLField(required=False, allow_blank=True, default="")
    external_reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    extracted_data = serializers.DictField(required=False, default=dict)
    tags = TagInputSerializer(many=True, required=False, default=list)
    request_verification = serializers.BooleanField(required=False, default=False)


class EvidenceUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True)
    external_reference = serializers.CharField(required=False, allow_blank=True, max_length=200)
    extracted_data = serializers.DictField(required=False)
    tags = TagInputSerializer(many=True, required=False)


def _tags(student, raw):
    ids = [t["skill_id"] for t in raw]
    skills = {s.pk: s for s in Skill.objects.filter(pk__in=ids, institution_id=student.institution_id)}
    if len(skills) != len(set(ids)):
        raise serializers.ValidationError({"tags": "Unknown skill."})
    return [(skills[t["skill_id"]], t["claimed_level"]) for t in raw]


class EvidenceViewSet(viewsets.ModelViewSet):
    """Students manage their own evidence; staff read evidence of students they can see."""

    serializer_class = EvidenceSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return EvidenceItem.objects.none()
        qs = (
            EvidenceItem.objects.filter(student__in=visible_students(self.request.user))
            .select_related("student__user")
            .prefetch_related(
                Prefetch("skill_tags", queryset=EvidenceSkillTag.objects.select_related("skill")),
                Prefetch("verifications", queryset=Verification.objects.select_related("reviewer")),
            )
        )
        if student := self.request.query_params.get("student"):
            qs = qs.filter(student_id=student)
        if st := self.request.query_params.get("status"):
            qs = qs.filter(verification_status=st)
        return qs

    @extend_schema(parameters=[OpenApiParameter("student", int), OpenApiParameter("status", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def _own_student(self):
        student = student_for_user(self.request.user)
        if student is None:
            raise PermissionDenied("Only students submit evidence.")
        return student

    def _own_item(self):
        item = self.get_object()
        if item.student.user_id != self.request.user.pk:
            raise PermissionDenied("You can only change your own evidence.")
        return item

    @extend_schema(request=EvidenceWriteSerializer, responses={201: EvidenceSerializer})
    def create(self, request, *args, **kwargs):
        student = self._own_student()
        data = EvidenceWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        tags = _tags(student, v.pop("tags"))
        item = service_call(
            services.submit_evidence, student=student, tags=tags, error_types=(services.EvidenceError,), **v
        )
        if v["request_verification"]:
            notify_verification_requested(item)
        return Response(EvidenceSerializer(self.get_queryset().get(pk=item.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=EvidenceUpdateSerializer, responses=EvidenceSerializer)
    def partial_update(self, request, *args, **kwargs):
        item = self._own_item()
        data = EvidenceUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        tags = _tags(item.student, v.pop("tags")) if "tags" in v else None
        service_call(services.update_evidence, item, tags=tags, error_types=(services.EvidenceError,), **v)
        return Response(EvidenceSerializer(self.get_queryset().get(pk=item.pk)).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        item = self._own_item()
        service_call(services.delete_evidence, item, error_types=(services.EvidenceError,))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=EvidenceSerializer)
    @action(detail=True, methods=["post"], url_path="request-verification")
    def request_verification(self, request, pk=None):
        item = self._own_item()
        service_call(services.request_verification, item, error_types=(services.EvidenceError,))
        notify_verification_requested(item)
        return Response(EvidenceSerializer(self.get_queryset().get(pk=item.pk)).data)
