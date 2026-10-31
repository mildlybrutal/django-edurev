from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.roles import Role, has_role
from apps.core.api import service_call
from apps.drives.models import Drive, DriveStatus
from apps.planning import services
from apps.planning.models import ItemStatus, LearningResource, PlanItem, PreparationPlan, ResourceKind
from apps.students.selectors import student_for_user, visible_students
from apps.taxonomy.models import POSITIVE_LEVEL_CHOICES, Skill


class PlanItemSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(source="skill.name", read_only=True, default=None)
    cluster = serializers.CharField(source="skill.cluster.slug", read_only=True, default=None)

    class Meta:
        model = PlanItem
        fields = [
            "id",
            "cluster",
            "skill",
            "title",
            "description",
            "resource_title",
            "resource_url",
            "start_date",
            "due_date",
            "is_checkpoint",
            "status",
            "completed_at",
            "order",
        ]


class PlanSerializer(serializers.ModelSerializer):
    items = PlanItemSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()
    drive_id = serializers.IntegerField(read_only=True)
    drive_date = serializers.DateField(source="drive.drive_date", read_only=True, default=None)
    company = serializers.CharField(source="drive.company.name", read_only=True, default=None)

    class Meta:
        model = PreparationPlan
        fields = [
            "id",
            "title",
            "drive_id",
            "drive_date",
            "company",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "progress",
            "items",
        ]

    def get_progress(self, obj) -> dict:
        return services.progress(obj)


class PlanSummarySerializer(PlanSerializer):
    class Meta(PlanSerializer.Meta):
        fields = [
            "id",
            "title",
            "drive_id",
            "drive_date",
            "company",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "progress",
        ]


class GenerateInput(serializers.Serializer):
    drive_id = serializers.IntegerField()


class ItemUpdateInput(serializers.Serializer):
    status = serializers.ChoiceField(choices=ItemStatus.choices)


class ResourceSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(source="skill.name", read_only=True)
    skill_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=ResourceKind.choices)
    target_level = serializers.ChoiceField(choices=POSITIVE_LEVEL_CHOICES)

    class Meta:
        model = LearningResource
        fields = ["id", "skill_id", "skill", "target_level", "title", "url", "kind", "estimated_hours"]


class PlanListView(ListAPIView):
    """GET /preparation-plans — the student's own plans, or (staff) plans of visible students."""

    serializer_class = PlanSummarySerializer

    def get_queryset(self):
        qs = (
            PreparationPlan.objects.filter(student__in=visible_students(self.request.user))
            .select_related("drive__company")
            .prefetch_related("items")
        )
        if student := self.request.query_params.get("student"):
            qs = qs.filter(student_id=student)
        if st := self.request.query_params.get("status"):
            qs = qs.filter(status=st)
        return qs

    @extend_schema(parameters=[OpenApiParameter("student", int), OpenApiParameter("status", str)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=GenerateInput, responses={201: PlanSerializer})
    def post(self, request):
        student = student_for_user(request.user)
        if student is None:
            raise PermissionDenied("Only students generate their own plans.")
        data = GenerateInput(data=request.data)
        data.is_valid(raise_exception=True)
        drive = (
            Drive.objects.filter(pk=data.validated_data["drive_id"], institution_id=student.institution_id)
            .exclude(status=DriveStatus.DRAFT)
            .first()
        )
        if drive is None:
            raise NotFound("Drive not found.")
        from apps.drives.api.views import evaluation_payload

        evaluation_payload(drive, student, refresh=False)  # make sure gaps are current
        plan = service_call(services.generate_plan, student, drive, error_types=(services.PlanError,))
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    @extend_schema(responses=PlanSerializer)
    def get(self, request, plan_id):
        plan = (
            PreparationPlan.objects.filter(pk=plan_id, student__in=visible_students(request.user))
            .select_related("drive__company")
            .prefetch_related("items__skill__cluster")
            .first()
        )
        if plan is None:
            raise NotFound()
        return Response(PlanSerializer(plan).data)


class PlanItemView(APIView):
    @extend_schema(request=ItemUpdateInput, responses=PlanItemSerializer)
    def patch(self, request, item_id):
        student = student_for_user(request.user)
        item = (
            PlanItem.objects.filter(pk=item_id, plan__student=student).select_related("plan").first()
            if student
            else None
        )
        if item is None:
            raise NotFound()
        data = ItemUpdateInput(data=request.data)
        data.is_valid(raise_exception=True)
        service_call(
            services.update_item_status, item, student, data.validated_data["status"], error_types=(services.PlanError,)
        )
        return Response(PlanItemSerializer(item).data)


class ResourceListView(ListAPIView):
    serializer_class = ResourceSerializer
    pagination_class = None

    def get_queryset(self):
        qs = LearningResource.objects.filter(institution_id=self.request.user.institution_id).select_related("skill")
        if skill := self.request.query_params.get("skill"):
            qs = qs.filter(skill_id=skill)
        return qs

    @extend_schema(request=ResourceSerializer, responses={201: ResourceSerializer})
    def post(self, request):
        if not has_role(request.user, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN, Role.FACULTY):
            raise PermissionDenied()
        data = ResourceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        skill = Skill.objects.filter(pk=v.pop("skill_id"), institution_id=request.user.institution_id).first()
        if skill is None:
            raise serializers.ValidationError({"skill_id": "Unknown skill."})
        resource = LearningResource.objects.create(institution_id=request.user.institution_id, skill=skill, **v)
        return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)
