from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import roles_required
from apps.accounts.roles import Role
from apps.core.api import service_call
from apps.evidence.api.views import EvidenceSerializer
from apps.evidence.models import EvidenceItem
from apps.verification import services
from apps.verification.models import Decision


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Decision.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class QueueView(APIView):
    """Faculty: evidence from their mentees awaiting verification, oldest first."""

    permission_classes = [roles_required(Role.FACULTY)]

    @extend_schema(responses=EvidenceSerializer(many=True))
    def get(self, request):
        return Response(EvidenceSerializer(services.pending_for_reviewer(request.user), many=True).data)


class DecideView(APIView):
    permission_classes = [roles_required(Role.FACULTY)]

    @extend_schema(request=DecisionSerializer, responses=EvidenceSerializer)
    def post(self, request, evidence_id):
        evidence = (
            EvidenceItem.objects.filter(
                pk=evidence_id, institution_id=request.user.institution_id, student__mentor=request.user
            )
            .select_related("student__user")
            .first()
        )
        if evidence is None:
            raise NotFound()
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        service_call(
            services.decide,
            evidence=evidence,
            reviewer=request.user,
            request=request,
            error_types=(services.VerificationError,),
            **data.validated_data,
        )
        evidence.refresh_from_db()
        return Response(EvidenceSerializer(evidence).data)
