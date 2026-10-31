from django.db.models import Prefetch
from django.utils.text import slugify
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response

from apps.accounts.roles import Role, has_role
from apps.core.api import InstitutionScopedMixin, get_scoped_or_404, service_call
from apps.core.services import record_audit
from apps.taxonomy import selectors, services
from apps.taxonomy.models import RoleSkill, Skill, SkillCluster, SkillRelation, SkillSynonym, TargetRole

from .serializers import (
    NameSerializer,
    RoleSkillSerializer,
    SkillClusterSerializer,
    SkillDetailSerializer,
    SkillIdSerializer,
    SkillSerializer,
    SkillUpdateSerializer,
    SkillWriteSerializer,
    TargetRoleSerializer,
)


class TaxonomyPermission(BasePermission):
    """Any signed-in member of the institution may read; only administrators change the
    taxonomy (P06 §6: Administrator owns the skill framework)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or has_role(request.user, Role.ADMIN)


def _taxonomy_error(fn, *args, **kwargs):
    return service_call(fn, *args, error_types=(services.TaxonomyError,), **kwargs)


class SkillViewSet(InstitutionScopedMixin, viewsets.ModelViewSet):
    permission_classes = [TaxonomyPermission]
    queryset = Skill.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related("cluster").prefetch_related("synonyms")
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch("parent_links", queryset=SkillRelation.objects.select_related("parent")),
                Prefetch("child_links", queryset=SkillRelation.objects.select_related("child")),
            )
        cluster = self.request.query_params.get("cluster")
        if cluster:
            qs = qs.filter(cluster__slug=cluster)
        return qs

    def get_serializer_class(self):
        return SkillDetailSerializer if self.action == "retrieve" else SkillSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Fuzzy search over names and synonyms (top 20, unpaginated)"),
            OpenApiParameter("cluster", str, description="Cluster slug"),
        ]
    )
    def list(self, request, *args, **kwargs):
        query = request.query_params.get("q")
        if query:
            results = selectors.search_skills(request.user.institution, query)
            cluster = request.query_params.get("cluster")
            if cluster:
                results = [s for s in results if s.cluster and s.cluster.slug == cluster]
            data = SkillSerializer(results, many=True).data
            return Response({"count": len(data), "next": None, "previous": None, "results": data})
        return super().list(request, *args, **kwargs)

    @extend_schema(request=SkillWriteSerializer, responses={201: SkillDetailSerializer})
    def create(self, request, *args, **kwargs):
        data = SkillWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        institution = request.user.institution
        cluster = self._cluster(data.validated_data.get("cluster_id"))
        parents = [self._skill(pk) for pk in data.validated_data["parent_ids"]]
        skill = _taxonomy_error(
            services.create_skill,
            institution=institution,
            name=data.validated_data["name"],
            description=data.validated_data["description"],
            is_abstract=data.validated_data["is_abstract"],
            cluster=cluster,
            parents=parents,
        )
        record_audit(
            actor=request.user,
            action="taxonomy.skill.create",
            target=skill,
            request=request,
            after={"name": skill.name},
        )
        return Response(SkillDetailSerializer(self._reload(skill)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=SkillUpdateSerializer, responses=SkillDetailSerializer)
    def partial_update(self, request, *args, **kwargs):
        skill = self.get_object()
        data = SkillUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        if "cluster_id" in changes:
            changes["cluster"] = self._cluster(changes.pop("cluster_id"))
        before = {"name": skill.name, "description": skill.description}
        _taxonomy_error(services.update_skill, skill, **changes)
        record_audit(
            actor=request.user,
            action="taxonomy.skill.update",
            target=skill,
            request=request,
            before=before,
            after={"name": skill.name, "description": skill.description},
        )
        return Response(SkillDetailSerializer(self._reload(skill)).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @extend_schema(responses={204: None})
    def destroy(self, request, *args, **kwargs):
        skill = self.get_object()
        # Skills are referenced by evidence, claims and requirements; retire rather than delete.
        skill.is_active = False
        skill.save(update_fields=["is_active", "updated_at"])
        record_audit(actor=request.user, action="taxonomy.skill.deactivate", target=skill, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=NameSerializer, responses={201: SkillDetailSerializer})
    @action(detail=True, methods=["post"])
    def synonyms(self, request, pk=None):
        skill = self.get_object()
        data = NameSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        synonym = _taxonomy_error(services.add_synonym, skill, data.validated_data["name"])
        record_audit(
            actor=request.user,
            action="taxonomy.synonym.add",
            target=skill,
            request=request,
            after={"synonym": synonym.name},
        )
        return Response(SkillDetailSerializer(self._reload(skill)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"synonyms/(?P<synonym_id>\d+)")
    def remove_synonym(self, request, pk=None, synonym_id=None):
        skill = self.get_object()
        synonym = get_scoped_or_404(SkillSynonym.objects.filter(skill=skill), skill.institution_id, pk=synonym_id)
        record_audit(
            actor=request.user,
            action="taxonomy.synonym.remove",
            target=skill,
            request=request,
            before={"synonym": synonym.name},
        )
        services.remove_synonym(synonym)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=SkillIdSerializer, responses={201: SkillDetailSerializer})
    @action(detail=True, methods=["post"])
    def parents(self, request, pk=None):
        skill = self.get_object()
        data = SkillIdSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        parent = self._skill(data.validated_data["skill_id"])
        _taxonomy_error(services.add_relation, skill, parent)
        record_audit(
            actor=request.user,
            action="taxonomy.relation.add",
            target=skill,
            request=request,
            after={"parent_id": parent.pk},
        )
        return Response(SkillDetailSerializer(self._reload(skill)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"parents/(?P<parent_id>\d+)")
    def remove_parent(self, request, pk=None, parent_id=None):
        skill = self.get_object()
        parent = self._skill(parent_id)
        services.remove_relation(skill, parent)
        record_audit(
            actor=request.user,
            action="taxonomy.relation.remove",
            target=skill,
            request=request,
            before={"parent_id": parent.pk},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=SkillIdSerializer, responses=SkillDetailSerializer)
    @action(detail=True, methods=["post"])
    def merge(self, request, pk=None):
        """Merge this skill into `skill_id`; this skill's name becomes a synonym of the target."""
        source = self.get_object()
        data = SkillIdSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        target = self._skill(data.validated_data["skill_id"])
        _taxonomy_error(services.merge_skills, source, target)
        record_audit(
            actor=request.user,
            action="taxonomy.skill.merge",
            target=source,
            request=request,
            after={"merged_into": target.pk},
        )
        return Response(SkillDetailSerializer(self._reload(target)).data)

    @extend_schema(
        parameters=[OpenApiParameter("name", str, required=True)],
        responses={200: SkillSerializer, 404: None},
    )
    @action(detail=False, methods=["get"])
    def resolve(self, request):
        """Exact name or synonym lookup, as used by JD processing and evidence tagging."""
        skill = selectors.resolve_skill(request.user.institution, request.query_params.get("name", ""))
        if skill is None:
            return Response({"detail": "No matching skill."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SkillSerializer(skill).data)

    def _skill(self, pk):
        return get_scoped_or_404(Skill.objects.filter(is_active=True), self.request.user.institution_id, pk=pk)

    def _cluster(self, pk):
        if pk is None:
            return None
        return get_scoped_or_404(SkillCluster.objects.all(), self.request.user.institution_id, pk=pk)

    def _reload(self, skill):
        return (
            Skill.objects.select_related("cluster")
            .prefetch_related(
                "synonyms",
                Prefetch("parent_links", queryset=SkillRelation.objects.select_related("parent")),
                Prefetch("child_links", queryset=SkillRelation.objects.select_related("child")),
            )
            .get(pk=skill.pk)
        )


class SkillClusterViewSet(InstitutionScopedMixin, viewsets.ModelViewSet):
    permission_classes = [TaxonomyPermission]
    serializer_class = SkillClusterSerializer
    queryset = SkillCluster.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        name = serializer.validated_data["name"]
        cluster = serializer.save(institution=self.request.user.institution, slug=slugify(name))
        record_audit(actor=self.request.user, action="taxonomy.cluster.create", target=cluster, request=self.request)

    def perform_update(self, serializer):
        cluster = serializer.save()
        record_audit(actor=self.request.user, action="taxonomy.cluster.update", target=cluster, request=self.request)

    def perform_destroy(self, instance):
        record_audit(actor=self.request.user, action="taxonomy.cluster.delete", target=instance, request=self.request)
        instance.delete()


class TargetRoleViewSet(InstitutionScopedMixin, viewsets.ModelViewSet):
    permission_classes = [TaxonomyPermission]
    serializer_class = TargetRoleSerializer
    queryset = TargetRole.objects.prefetch_related(
        Prefetch("role_skills", queryset=RoleSkill.objects.select_related("skill"))
    )
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        role = serializer.save(
            institution=self.request.user.institution, slug=slugify(serializer.validated_data["name"])
        )
        record_audit(actor=self.request.user, action="taxonomy.role.create", target=role, request=self.request)

    def perform_update(self, serializer):
        role = serializer.save()
        record_audit(actor=self.request.user, action="taxonomy.role.update", target=role, request=self.request)

    def perform_destroy(self, instance):
        record_audit(actor=self.request.user, action="taxonomy.role.delete", target=instance, request=self.request)
        instance.delete()

    @extend_schema(request=RoleSkillSerializer, responses={201: TargetRoleSerializer})
    @action(detail=True, methods=["post"], url_path="skills")
    def add_skill(self, request, pk=None):
        role = self.get_object()
        data = RoleSkillSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        skill = get_scoped_or_404(
            Skill.objects.filter(is_active=True), request.user.institution_id, pk=data.validated_data.pop("skill_id")
        )
        RoleSkill.objects.update_or_create(
            role=role, skill=skill, defaults={**data.validated_data, "institution": role.institution}
        )
        record_audit(
            actor=request.user,
            action="taxonomy.role.skill.set",
            target=role,
            request=request,
            after={"skill_id": skill.pk, **data.validated_data},
        )
        return Response(TargetRoleSerializer(self.get_queryset().get(pk=role.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"skills/(?P<skill_id>\d+)")
    def remove_skill(self, request, pk=None, skill_id=None):
        role = self.get_object()
        deleted, _ = RoleSkill.objects.filter(role=role, skill_id=skill_id).delete()
        if deleted:
            record_audit(
                actor=request.user,
                action="taxonomy.role.skill.remove",
                target=role,
                request=request,
                before={"skill_id": int(skill_id)},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
