from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.roles import user_roles
from apps.accounts.services import mfa_device, mfa_setup_required


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class InstitutionSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()


class MFAStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    setup_required = serializers.BooleanField()


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    roles = serializers.SerializerMethodField()
    institution = InstitutionSummarySerializer(allow_null=True)
    mfa = serializers.SerializerMethodField()

    def get_roles(self, user) -> list[str]:
        return sorted(user_roles(user))

    @extend_schema_field(MFAStatusSerializer)
    def get_mfa(self, user):
        return {"enabled": mfa_device(user) is not None, "setup_required": mfa_setup_required(user)}


class MFACodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=10)


class MFASetupSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()


class LoginResultSerializer(MeSerializer):
    mfa_required = serializers.BooleanField(required=False)
