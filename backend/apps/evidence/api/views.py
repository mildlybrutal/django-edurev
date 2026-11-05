from django.conf import settings
from django.db.models import Prefetch
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.api import service_call
from apps.core.services import record_audit
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


class CertificateFileSerializer(serializers.Serializer):
    name = serializers.CharField(source="original_name")
    content_type = serializers.CharField()
    size = serializers.IntegerField()
    uploaded_at = serializers.DateTimeField(source="created_at")


class EvidenceSerializer(serializers.ModelSerializer):
    skill_tags = TagSerializer(many=True, read_only=True)
    verifications = VerificationSerializer(many=True, read_only=True)
    source_label = serializers.CharField(source="get_source_type_display", read_only=True)
    status_label = serializers.CharField(source="get_verification_status_display", read_only=True)
    student_id = serializers.IntegerField(read_only=True)
    student_name = serializers.CharField(source="student.name", read_only=True)
    is_institutional = serializers.SerializerMethodField()
    certificate = serializers.SerializerMethodField()

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
            "certificate",
        ]

    @extend_schema_field(CertificateFileSerializer(allow_null=True))
    def get_certificate(self, obj):
        attached = getattr(obj, "file", None)
        return CertificateFileSerializer(attached).data if attached is not None else None

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return EvidenceItem.objects.none()
        qs = (
            EvidenceItem.objects.filter(student__in=visible_students(self.request.user))
            .select_related("student__user", "file")
            .prefetch_related(
                Prefetch("skill_tags", queryset=EvidenceSkillTag.objects.select_related("skill")),
                Prefetch("verifications", queryset=Verification.objects.select_related("reviewer")),
            )
        )
        if student := self.request.query_params.get("student"):
            qs = qs.filter(student_id=student)
        if st := self.request.query_params.get("status"):
            qs = qs.filter(verification_status=st)
        if source := self.request.query_params.get("source_type"):
            qs = qs.filter(source_type=source)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("student", int),
            OpenApiParameter("status", str),
            OpenApiParameter("source_type", str),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter("student", int),
            OpenApiParameter("status", str),
            OpenApiParameter("source_type", str),
        ],
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    @action(detail=False, methods=["get"])
    def export(self, request):
        """Staff-only Excel sheet of the evidence they can see (faculty: mentees), filtered by
        student, verification status or source type. Files and links to files are not included."""
        from apps.accounts.roles import Role, has_role
        from apps.core.excel import workbook_response

        if not has_role(request.user, Role.FACULTY, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN):
            raise PermissionDenied()
        items = list(
            self.get_queryset().select_related("student__department").order_by("student__roll_number", "-submitted_at")
        )

        def last_review(item):
            reviews = sorted(item.verifications.all(), key=lambda v: v.created_at)
            if not reviews:
                return ""
            v = reviews[-1]
            return f"{v.get_decision_display()} by {v.reviewer.get_full_name() or v.reviewer.email}"

        columns = [
            ("Registration number", lambda e: e.student.roll_number),
            ("Student", lambda e: e.student.name),
            ("Department", lambda e: e.student.department.code),
            ("Source", lambda e: e.get_source_type_display()),
            ("Title", lambda e: e.title),
            ("Verification status", lambda e: e.get_verification_status_display()),
            (
                "Skills claimed",
                lambda e: [f"{t.skill.name} ({Level(t.claimed_level).label})" for t in e.skill_tags.all()],
            ),
            ("Certificate file", lambda e: getattr(e, "file", None) is not None),
            ("External reference", lambda e: e.external_reference),
            ("Submitted", lambda e: e.submitted_at),
            ("Last review", last_review),
        ]
        record_audit(
            actor=request.user,
            action="evidence.export",
            request=request,
            after={"rows": len(items), "filters": dict(request.query_params.items())},
        )
        return workbook_response("evidence", [("Evidence", columns, items)])

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

    @extend_schema(
        methods=["GET"],
        responses=OpenApiTypes.OBJECT,
        description="Short-lived view link for the certificate file (student, mentor, placement cell).",
    )
    @extend_schema(
        methods=["POST"],
        request={
            "multipart/form-data": {"type": "object", "properties": {"file": {"type": "string", "format": "binary"}}}
        },
        responses=EvidenceSerializer,
        description="Attach or replace the certificate (PDF, PNG or JPEG) of your own certification evidence.",
    )
    @extend_schema(methods=["DELETE"], responses={204: None})
    @action(detail=True, methods=["get", "post", "delete"], url_path="certificate")
    def certificate(self, request, pk=None):
        from apps.evidence.files import CertificateFileError, certificate_url

        if request.method == "GET":
            item = self.get_object()
            attached = getattr(item, "file", None)
            if attached is None:
                return Response({"detail": "No certificate uploaded."}, status=status.HTTP_404_NOT_FOUND)
            if item.student.user_id != request.user.pk:
                record_audit(actor=request.user, action="evidence.certificate.view", target=item, request=request)
            response = Response(
                {
                    "name": attached.original_name,
                    "content_type": attached.content_type,
                    "url": certificate_url(attached),
                    "expires_in": settings.RESUME_URL_EXPIRY_SECONDS,
                }
            )
            response["Cache-Control"] = "no-store"
            return response
        item = self._own_item()
        if request.method == "DELETE":
            service_call(services.remove_certificate, item, actor=request.user, error_types=(services.EvidenceError,))
            return Response(status=status.HTTP_204_NO_CONTENT)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"detail": "Choose a file to upload."}, status=status.HTTP_400_BAD_REQUEST)
        service_call(
            services.attach_certificate,
            item,
            uploaded,
            uploaded_by=request.user,
            error_types=(services.EvidenceError, CertificateFileError),
        )
        return Response(EvidenceSerializer(self.get_queryset().get(pk=item.pk)).data, status=status.HTTP_201_CREATED)
