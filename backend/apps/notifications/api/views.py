from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notifications import services
from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "created_at", "read_at"]


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class UnreadCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """The signed-in user's own notifications only."""

    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @extend_schema(responses=UnreadCountSerializer)
    @action(detail=False, methods=["get"])
    def unread(self, request):
        return Response({"unread": self.get_queryset().filter(read_at__isnull=True).count()})

    @extend_schema(request=MarkReadSerializer, responses=UnreadCountSerializer)
    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request):
        data = MarkReadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.mark_read(request.user, data.validated_data.get("ids"))
        return Response({"unread": self.get_queryset().filter(read_at__isnull=True).count()})
