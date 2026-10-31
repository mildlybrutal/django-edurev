from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.taxonomy.models import Level, RoleSkill, Skill, SkillCluster, SkillSynonym, TargetRole


class SkillClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillCluster
        fields = ["id", "name", "slug", "description"]
        read_only_fields = ["slug"]


class SkillRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "slug"]


class SkillSynonymSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillSynonym
        fields = ["id", "name"]


class SkillSerializer(serializers.ModelSerializer):
    cluster = SkillClusterSerializer(read_only=True)
    synonyms = SkillSynonymSerializer(many=True, read_only=True)

    class Meta:
        model = Skill
        fields = ["id", "name", "slug", "description", "is_abstract", "cluster", "synonyms"]


class SkillDetailSerializer(SkillSerializer):
    parents = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta(SkillSerializer.Meta):
        fields = [*SkillSerializer.Meta.fields, "parents", "children"]

    @extend_schema_field(SkillRefSerializer(many=True))
    def get_parents(self, skill):
        return SkillRefSerializer([link.parent for link in skill.parent_links.all()], many=True).data

    @extend_schema_field(SkillRefSerializer(many=True))
    def get_children(self, skill):
        return SkillRefSerializer([link.child for link in skill.child_links.all()], many=True).data


class SkillWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_abstract = serializers.BooleanField(required=False, default=False)
    cluster_id = serializers.IntegerField(required=False, allow_null=True)
    parent_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class SkillUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_abstract = serializers.BooleanField(required=False)
    cluster_id = serializers.IntegerField(required=False, allow_null=True)


class NameSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)


class SkillIdSerializer(serializers.Serializer):
    skill_id = serializers.IntegerField()


class RoleSkillSerializer(serializers.ModelSerializer):
    skill = SkillRefSerializer(read_only=True)
    skill_id = serializers.IntegerField(write_only=True)
    required_level_label = serializers.SerializerMethodField()

    class Meta:
        model = RoleSkill
        fields = ["id", "skill", "skill_id", "required_level", "required_level_label", "weight", "is_core"]

    def get_required_level_label(self, obj) -> str:
        return Level(obj.required_level).label


class TargetRoleSerializer(serializers.ModelSerializer):
    role_skills = RoleSkillSerializer(many=True, read_only=True)

    class Meta:
        model = TargetRole
        fields = ["id", "name", "slug", "description", "role_skills"]
        read_only_fields = ["slug"]
