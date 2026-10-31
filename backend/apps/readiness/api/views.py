from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import roles_required
from apps.accounts.roles import Role, has_role
from apps.core.api import service_call
from apps.core.services import record_audit
from apps.profiles.models import EvidenceRule
from apps.profiles.services import rules_for
from apps.readiness import services
from apps.readiness.models import ScoringConfig
from apps.taxonomy.models import Level

STAFF = (Role.FACULTY, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN)


class ScoringConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringConfig
        fields = [
            "id",
            "version",
            "is_active",
            "weight_technical",
            "weight_aptitude",
            "weight_communication",
            "weight_project_depth",
            "weight_coding",
            "unverified_multiplier",
            "technical_top_n",
            "recent_window",
            "project_target",
            "ready_threshold",
            "created_at",
        ]
        read_only_fields = ["id", "version", "is_active", "created_at"]


class EvidenceRuleSerializer(serializers.ModelSerializer):
    source_label = serializers.CharField(source="get_source_type_display", read_only=True)

    class Meta:
        model = EvidenceRule
        fields = ["id", "source_type", "source_label", "max_level_unverified", "max_level_verified"]
        read_only_fields = ["id", "source_type"]

    def validate(self, attrs):
        unverified = attrs.get("max_level_unverified", getattr(self.instance, "max_level_unverified", 0))
        verified = attrs.get("max_level_verified", getattr(self.instance, "max_level_verified", 0))
        if unverified > verified:
            raise serializers.ValidationError("Unverified evidence cannot be allowed a higher level than verified.")
        if verified not in Level.values:
            raise serializers.ValidationError("Unknown level.")
        return attrs


class ScoringConfigView(APIView):
    """Readiness model settings (P06 §9). Any staff member can read; administrators publish
    a new version, which applies to snapshots computed from then on."""

    permission_classes = [roles_required(*STAFF)]

    @extend_schema(responses=ScoringConfigSerializer)
    def get(self, request):
        return Response(ScoringConfigSerializer(services.active_config(request.user.institution_id)).data)

    @extend_schema(request=ScoringConfigSerializer, responses={201: ScoringConfigSerializer})
    def post(self, request):
        if not has_role(request.user, Role.ADMIN):
            raise PermissionDenied()
        data = ScoringConfigSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        config = service_call(
            services.publish_config,
            institution=request.user.institution,
            created_by=request.user,
            error_types=(services.ReadinessError,),
            **data.validated_data,
        )
        record_audit(
            actor=request.user,
            action="readiness.config.publish",
            target=config,
            request=request,
            after={k: str(v) for k, v in data.validated_data.items()},
        )
        return Response(ScoringConfigSerializer(config).data, status=status.HTTP_201_CREATED)


class EvidenceRuleListView(APIView):
    permission_classes = [roles_required(*STAFF)]

    @extend_schema(responses=EvidenceRuleSerializer(many=True))
    def get(self, request):
        rules = sorted(rules_for(request.user.institution_id).values(), key=lambda r: r.source_type)
        return Response(EvidenceRuleSerializer(rules, many=True).data)


class EvidenceRuleDetailView(APIView):
    permission_classes = [roles_required(Role.ADMIN)]

    @extend_schema(request=EvidenceRuleSerializer, responses=EvidenceRuleSerializer)
    def patch(self, request, rule_id):
        rule = EvidenceRule.objects.filter(pk=rule_id, institution_id=request.user.institution_id).first()
        if rule is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        before = {"unverified": rule.max_level_unverified, "verified": rule.max_level_verified}
        data = EvidenceRuleSerializer(rule, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        record_audit(
            actor=request.user,
            action="profiles.evidence_rule.update",
            target=rule,
            request=request,
            before=before,
            after={"unverified": rule.max_level_unverified, "verified": rule.max_level_verified},
        )
        return Response(data.data)
