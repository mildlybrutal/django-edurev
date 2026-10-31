from django.contrib import admin

from .models import RoleSkill, Skill, SkillCluster, SkillRelation, SkillSynonym, TargetRole


class SynonymInline(admin.TabularInline):
    model = SkillSynonym
    fields = ["name"]
    extra = 0


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "cluster", "is_abstract", "is_active", "institution"]
    list_filter = ["institution", "cluster", "is_abstract", "is_active"]
    search_fields = ["name", "synonyms__name"]
    readonly_fields = ["normalized_name", "merged_into"]
    inlines = [SynonymInline]

    def has_add_permission(self, request):
        # Create skills through the API so names, synonyms and the closure stay consistent.
        return False


@admin.register(SkillCluster)
class SkillClusterAdmin(admin.ModelAdmin):
    list_display = ["name", "institution"]
    list_filter = ["institution"]


@admin.register(SkillRelation)
class SkillRelationAdmin(admin.ModelAdmin):
    list_display = ["child", "parent", "institution"]
    list_filter = ["institution"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class RoleSkillInline(admin.TabularInline):
    model = RoleSkill
    fields = ["skill", "required_level", "weight", "is_core"]
    autocomplete_fields = ["skill"]
    extra = 0


@admin.register(TargetRole)
class TargetRoleAdmin(admin.ModelAdmin):
    list_display = ["name", "institution"]
    list_filter = ["institution"]
    inlines = [RoleSkillInline]
