"""Placement head: recruiter accounts, access grants and access-log review (internal portal)."""

from django.contrib.auth import get_user_model
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import roles_required
from apps.accounts.roles import Role
from apps.core.api import service_call
from apps.drives.models import Drive
from apps.recruiter import services
from apps.recruiter.models import RELEASABLE_FIELDS, AccessLog, CandidateScope, RecruiterAccessGrant, RecruiterBroadcast

HEAD = roles_required(Role.PLACEMENT_HEAD)


class RecruiterSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, min_length=10)
    is_active = serializers.BooleanField(read_only=True)


class GrantSerializer(serializers.ModelSerializer):
    recruiter_email = serializers.EmailField(source="recruiter.email", read_only=True)
    drive_label = serializers.CharField(source="drive.__str__", read_only=True)
    recruiter_id = serializers.IntegerField()
    drive_id = serializers.IntegerField()
    is_valid = serializers.SerializerMethodField()
    allowed_fields = serializers.ListField(child=serializers.ChoiceField(choices=list(RELEASABLE_FIELDS)))
    candidate_scope = serializers.ChoiceField(choices=CandidateScope.choices, default=CandidateScope.REGISTERED)

    class Meta:
        model = RecruiterAccessGrant
        fields = [
            "id",
            "recruiter_id",
            "recruiter_email",
            "drive_id",
            "drive_label",
            "allowed_fields",
            "candidate_scope",
            "starts_at",
            "expires_at",
            "status",
            "is_valid",
            "created_at",
            "revoked_at",
        ]
        read_only_fields = ["status", "created_at", "revoked_at"]

    def get_is_valid(self, obj) -> bool:
        return obj.is_valid()


class GrantUpdateSerializer(serializers.Serializer):
    allowed_fields = serializers.ListField(
        child=serializers.ChoiceField(choices=list(RELEASABLE_FIELDS)), required=False
    )
    expires_at = serializers.DateTimeField(required=False)
    candidate_scope = serializers.ChoiceField(choices=CandidateScope.choices, required=False)


class AccessLogSerializer(serializers.ModelSerializer):
    recruiter_email = serializers.EmailField(source="recruiter.email", read_only=True)

    class Meta:
        model = AccessLog
        fields = [
            "id",
            "created_at",
            "recruiter_id",
            "recruiter_email",
            "grant_id",
            "drive_id_requested",
            "action",
            "path",
            "query",
            "student_ids",
            "fields_released",
            "ip",
        ]


def _grant_error(fn, *args, **kwargs):
    return service_call(fn, *args, error_types=(services.GrantError,), **kwargs)


class ReleasableFieldsView(APIView):
    permission_classes = [HEAD]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response([{"field": k, "label": v} for k, v in RELEASABLE_FIELDS.items()])


class RecruiterListView(APIView):
    permission_classes = [HEAD]

    @extend_schema(responses=RecruiterSerializer(many=True))
    def get(self, request):
        users = (
            get_user_model()
            .objects.filter(institution_id=request.user.institution_id, groups__name=Role.RECRUITER)
            .order_by("email")
        )
        return Response(
            [
                {
                    "id": u.pk,
                    "email": u.email,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "is_active": u.is_active,
                }
                for u in users
            ]
        )

    @extend_schema(request=RecruiterSerializer, responses={201: RecruiterSerializer})
    def post(self, request):
        data = RecruiterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = _grant_error(
            services.create_recruiter,
            institution=request.user.institution,
            created_by=request.user,
            request=request,
            **data.validated_data,
        )
        return Response(
            {
                "id": user.pk,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
            },
            status=status.HTTP_201_CREATED,
        )


class GrantListView(ListAPIView):
    serializer_class = GrantSerializer
    permission_classes = [HEAD]

    def get_queryset(self):
        qs = RecruiterAccessGrant.objects.filter(institution_id=self.request.user.institution_id).select_related(
            "recruiter", "drive__company"
        )
        if drive := self.request.query_params.get("drive"):
            qs = qs.filter(drive_id=drive)
        return qs

    @extend_schema(request=GrantSerializer, responses={201: GrantSerializer})
    def post(self, request):
        data = GrantSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        recruiter = (
            get_user_model().objects.filter(pk=v["recruiter_id"], institution_id=request.user.institution_id).first()
        )
        drive = Drive.objects.filter(pk=v["drive_id"], institution_id=request.user.institution_id).first()
        if recruiter is None or drive is None:
            raise serializers.ValidationError({"detail": "Unknown recruiter or drive."})
        grant = _grant_error(
            services.create_grant,
            recruiter=recruiter,
            drive=drive,
            allowed_fields=v["allowed_fields"],
            expires_at=v["expires_at"],
            starts_at=v.get("starts_at"),
            candidate_scope=v["candidate_scope"],
            granted_by=request.user,
            request=request,
        )
        return Response(GrantSerializer(grant).data, status=status.HTTP_201_CREATED)


class GrantDetailView(APIView):
    permission_classes = [HEAD]

    def _grant(self, request, grant_id):
        grant = RecruiterAccessGrant.objects.filter(pk=grant_id, institution_id=request.user.institution_id).first()
        if grant is None:
            raise NotFound()
        return grant

    @extend_schema(request=GrantUpdateSerializer, responses=GrantSerializer)
    def patch(self, request, grant_id):
        grant = self._grant(request, grant_id)
        data = GrantUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        _grant_error(services.update_grant, grant, actor=request.user, request=request, **data.validated_data)
        return Response(GrantSerializer(grant).data)

    @extend_schema(request=None, responses=GrantSerializer)
    def delete(self, request, grant_id):
        grant = self._grant(request, grant_id)
        services.revoke_grant(grant, actor=request.user, request=request)
        return Response(GrantSerializer(grant).data)


class AccessLogListView(ListAPIView):
    serializer_class = AccessLogSerializer
    permission_classes = [HEAD]

    def get_queryset(self):
        qs = AccessLog.objects.filter(institution_id=self.request.user.institution_id).select_related("recruiter")
        params = self.request.query_params
        if recruiter := params.get("recruiter"):
            qs = qs.filter(recruiter_id=recruiter)
        if drive := params.get("drive"):
            qs = qs.filter(drive_id_requested=drive)
        if action := params.get("action"):
            qs = qs.filter(action=action)
        return qs

    @extend_schema(
        parameters=[OpenApiParameter("recruiter", int), OpenApiParameter("drive", int), OpenApiParameter("action", str)]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BroadcastLogSerializer(serializers.ModelSerializer):
    recruiter_email = serializers.EmailField(source="recruiter.email", read_only=True)
    drive_label = serializers.CharField(source="drive.__str__", read_only=True)

    class Meta:
        model = RecruiterBroadcast
        fields = [
            "id",
            "recruiter_email",
            "drive_id",
            "drive_label",
            "audience",
            "title",
            "body",
            "recipient_count",
            "created_at",
            "sent_at",
        ]


class BroadcastLogListView(ListAPIView):
    """Placement head review of every recruiter broadcast in the institution."""

    serializer_class = BroadcastLogSerializer
    permission_classes = [HEAD]

    def get_queryset(self):
        qs = RecruiterBroadcast.objects.filter(institution_id=self.request.user.institution_id).select_related(
            "recruiter", "drive__company"
        )
        if drive := self.request.query_params.get("drive"):
            qs = qs.filter(drive_id=drive)
        return qs

    @extend_schema(parameters=[OpenApiParameter("drive", int)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
