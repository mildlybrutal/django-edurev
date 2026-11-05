from django.db.models import Max, Prefetch
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response

from apps.accounts.roles import Role, has_role
from apps.core.api import service_call
from apps.core.models import BackgroundJob
from apps.drives import services
from apps.drives.models import (
    Company,
    Drive,
    DriveRequirement,
    DriveStatus,
    EligibilityResult,
    EligibilityRule,
    Registration,
    RegistrationStatus,
    RuleType,
)
from apps.matching import services as matching_services
from apps.matching.models import GapAnalysis, GapItem, MatchResult
from apps.planning.models import PlanStatus, PreparationPlan
from apps.profiles.models import SkillClaim
from apps.readiness.models import ReadinessSnapshot
from apps.readiness.services import active_config
from apps.students.api.views import snapshot_data
from apps.students.selectors import student_for_user
from apps.taxonomy.models import POSITIVE_LEVEL_CHOICES, Level, Skill, TargetRole

CELL = (Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD)


def is_cell(user):
    return has_role(user, *CELL)


class DrivePermission(BasePermission):
    """Placement officers/heads manage drives. Students read published drives. Anyone else: none."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if is_cell(user):
            return True
        return request.method in SAFE_METHODS or getattr(view, "action", None) in ("register", "withdraw")


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "website", "description"]


class RequirementSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(source="skill.name", read_only=True)
    skill_id = serializers.IntegerField()
    level_label = serializers.SerializerMethodField()

    class Meta:
        model = DriveRequirement
        fields = ["id", "skill_id", "skill", "required_level", "level_label", "weight", "is_mandatory", "source"]
        read_only_fields = ["source"]

    def get_level_label(self, obj) -> str:
        return Level(obj.required_level).label


class RuleSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_rule_type_display", read_only=True)

    class Meta:
        model = EligibilityRule
        fields = ["rule_type", "label", "value"]


class DriveSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.IntegerField(write_only=True)
    target_role_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    requirements = RequirementSerializer(many=True, read_only=True)
    eligibility_rules = RuleSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    registration_open = serializers.SerializerMethodField()

    class Meta:
        model = Drive
        fields = [
            "id",
            "company",
            "company_id",
            "role_title",
            "target_role_id",
            "location",
            "compensation",
            "job_description",
            "jd_status",
            "status",
            "status_label",
            "registration_opens_at",
            "registration_closes_at",
            "drive_date",
            "registration_open",
            "last_matched_at",
            "requirements",
            "eligibility_rules",
            "created_at",
        ]
        read_only_fields = ["job_description", "jd_status", "status", "last_matched_at", "created_at"]

    def get_registration_open(self, obj) -> bool:
        return services.registration_open(obj)


class DriveUpdateSerializer(serializers.Serializer):
    role_title = serializers.CharField(max_length=200, required=False)
    location = serializers.CharField(max_length=150, required=False, allow_blank=True)
    compensation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    registration_opens_at = serializers.DateTimeField(required=False, allow_null=True)
    registration_closes_at = serializers.DateTimeField(required=False, allow_null=True)
    drive_date = serializers.DateField(required=False, allow_null=True)


class JDInput(serializers.Serializer):
    text = serializers.CharField()


class JDApplySkill(serializers.Serializer):
    skill_id = serializers.IntegerField()
    required_level = serializers.ChoiceField(choices=POSITIVE_LEVEL_CHOICES)
    weight = serializers.IntegerField(min_value=1, max_value=10)
    is_mandatory = serializers.BooleanField()


class JDApplyRule(serializers.Serializer):
    rule_type = serializers.ChoiceField(choices=RuleType.choices)
    value = serializers.JSONField()


class JDApplyInput(serializers.Serializer):
    skills = JDApplySkill(many=True)
    rules = JDApplyRule(many=True)


class TransitionInput(serializers.Serializer):
    status = serializers.ChoiceField(choices=DriveStatus.choices)


class RoleInput(serializers.Serializer):
    role_id = serializers.IntegerField()


class DecisionInput(serializers.Serializer):
    status = serializers.ChoiceField(choices=sorted(services.OFFICER_DECISIONS))


class JobSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = BackgroundJob
        fields = [
            "id",
            "kind",
            "status",
            "total",
            "processed",
            "result",
            "error",
            "created_at",
            "started_at",
            "finished_at",
            "duration_seconds",
        ]


def _drive_error(fn, *args, **kwargs):
    return service_call(fn, *args, error_types=(services.DriveError,), **kwargs)


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Company.objects.none()
        return Company.objects.filter(institution_id=self.request.user.institution_id)

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in SAFE_METHODS and not is_cell(request.user):
            raise PermissionDenied()

    def perform_create(self, serializer):
        serializer.save(institution_id=self.request.user.institution_id)


class DriveViewSet(viewsets.ModelViewSet):
    serializer_class = DriveSerializer
    permission_classes = [DrivePermission]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Drive.objects.none()
        qs = (
            Drive.objects.filter(institution_id=self.request.user.institution_id)
            .select_related("company")
            .prefetch_related(
                Prefetch("requirements", queryset=DriveRequirement.objects.select_related("skill")), "eligibility_rules"
            )
        )
        if not is_cell(self.request.user):
            # Students (and other roles) never see drafts.
            qs = qs.exclude(status=DriveStatus.DRAFT)
        if st := self.request.query_params.get("status"):
            qs = qs.filter(status=st)
        return qs

    @extend_schema(parameters=[OpenApiParameter("status", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        data = DriveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        company = Company.objects.filter(pk=v.pop("company_id"), institution_id=request.user.institution_id).first()
        if company is None:
            raise serializers.ValidationError({"company_id": "Unknown company."})
        role_id = v.pop("target_role_id", None)
        if role_id is not None:
            v["target_role"] = TargetRole.objects.filter(pk=role_id, institution_id=request.user.institution_id).first()
            if v["target_role"] is None:
                raise serializers.ValidationError({"target_role_id": "Unknown target role."})
        drive = _drive_error(
            services.create_drive,
            institution=request.user.institution,
            company=company,
            created_by=request.user,
            request=request,
            **v,
        )
        return Response(DriveSerializer(self.get_queryset().get(pk=drive.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=DriveUpdateSerializer, responses=DriveSerializer)
    def partial_update(self, request, *args, **kwargs):
        drive = self.get_object()
        data = DriveUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        _drive_error(services.update_drive, drive, actor=request.user, request=request, **data.validated_data)
        return Response(DriveSerializer(self.get_queryset().get(pk=drive.pk)).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        drive = self.get_object()
        if drive.status != DriveStatus.DRAFT:
            raise serializers.ValidationError({"detail": "Only draft drives can be deleted; cancel it instead."})
        drive.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _reload(self, drive):
        return Response(DriveSerializer(self.get_queryset().get(pk=drive.pk)).data)

    # --- requirements and eligibility -------------------------------------------------------

    @extend_schema(request=RequirementSerializer, responses=DriveSerializer)
    @action(detail=True, methods=["post"])
    def requirements(self, request, pk=None):
        drive = self.get_object()
        data = RequirementSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        skill = Skill.objects.filter(pk=v["skill_id"], institution_id=drive.institution_id).first()
        if skill is None:
            raise serializers.ValidationError({"skill_id": "Unknown skill."})
        _drive_error(
            services.set_requirement,
            drive,
            skill=skill,
            required_level=v["required_level"],
            weight=v["weight"],
            is_mandatory=v["is_mandatory"],
        )
        return self._reload(drive)

    @extend_schema(request=None, responses=DriveSerializer)
    @action(detail=True, methods=["delete"], url_path=r"requirements/(?P<skill_id>\d+)")
    def remove_requirement(self, request, pk=None, skill_id=None):
        drive = self.get_object()
        _drive_error(services.remove_requirement, drive, int(skill_id))
        return self._reload(drive)

    @extend_schema(request=RuleSerializer, responses=DriveSerializer)
    @action(detail=True, methods=["post"], url_path="eligibility-rules")
    def eligibility_rules(self, request, pk=None):
        drive = self.get_object()
        data = RuleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        _drive_error(
            services.set_eligibility_rule, drive, data.validated_data["rule_type"], data.validated_data["value"]
        )
        return self._reload(drive)

    @extend_schema(request=None, responses=DriveSerializer)
    @action(detail=True, methods=["delete"], url_path=r"eligibility-rules/(?P<rule_type>[a-z_]+)")
    def remove_eligibility_rule(self, request, pk=None, rule_type=None):
        drive = self.get_object()
        _drive_error(services.remove_eligibility_rule, drive, rule_type)
        return self._reload(drive)

    @extend_schema(request=RoleInput, responses=DriveSerializer)
    @action(detail=True, methods=["post"], url_path="apply-role")
    def apply_role(self, request, pk=None):
        drive = self.get_object()
        data = RoleInput(data=request.data)
        data.is_valid(raise_exception=True)
        role = TargetRole.objects.filter(pk=data.validated_data["role_id"], institution_id=drive.institution_id).first()
        if role is None:
            raise NotFound()
        _drive_error(services.apply_role_template, drive, role)
        return self._reload(drive)

    # --- JD ---------------------------------------------------------------------------------

    @extend_schema(request=JDInput, responses=DriveSerializer)
    @action(detail=True, methods=["get", "post"])
    def jd(self, request, pk=None):
        drive = self.get_object()
        if request.method == "GET":
            return Response(
                {"status": drive.jd_status, "text": drive.job_description, "extraction": drive.jd_extraction}
            )
        data = JDInput(data=request.data)
        data.is_valid(raise_exception=True)
        _drive_error(services.submit_jd, drive, data.validated_data["text"])
        return Response(
            {"status": drive.jd_status, "text": drive.job_description, "extraction": {}},
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(request=JDApplyInput, responses=DriveSerializer)
    @action(detail=True, methods=["post"], url_path="jd/apply")
    def jd_apply(self, request, pk=None):
        drive = self.get_object()
        data = JDApplyInput(data=request.data)
        data.is_valid(raise_exception=True)
        _drive_error(services.apply_jd_extraction, drive, actor=request.user, request=request, **data.validated_data)
        return self._reload(drive)

    # --- lifecycle --------------------------------------------------------------------------

    @extend_schema(request=TransitionInput, responses=DriveSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        drive = self.get_object()
        data = TransitionInput(data=request.data)
        data.is_valid(raise_exception=True)
        _drive_error(services.transition, drive, data.validated_data["status"], actor=request.user, request=request)
        return self._reload(drive)

    # --- matching (officer) -----------------------------------------------------------------

    @extend_schema(
        parameters=[
            OpenApiParameter("eligible", bool),
            OpenApiParameter("registered", bool),
            OpenApiParameter("min_compatibility", float),
            OpenApiParameter("q", str),
        ],
        request=None,
    )
    @action(detail=True, methods=["get", "post"])
    def match(self, request, pk=None):
        """POST starts a background matching job (eligibility + compatibility + readiness + gaps
        for every student). GET lists results, eligibility and compatibility side by side."""
        drive = self.get_object()
        if not is_cell(request.user):
            raise PermissionDenied()
        if request.method == "POST":
            job = matching_services.start_drive_matching_job(drive, created_by=request.user)
            return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
        return Response(_match_rows(drive, request.query_params))

    @extend_schema(responses=JobSerializer(many=True))
    @action(detail=True, methods=["get"], pagination_class=None)
    def jobs(self, request, pk=None):
        drive = self.get_object()
        if not is_cell(request.user):
            raise PermissionDenied()
        jobs = BackgroundJob.objects.filter(
            institution_id=drive.institution_id, kind="drive_matching", params__drive_id=drive.pk
        )[:5]
        return Response(JobSerializer(jobs, many=True).data)

    @action(detail=True, methods=["get"], url_path=r"students/(?P<student_id>\d+)")
    def student_evaluation(self, request, pk=None, student_id=None):
        drive = self.get_object()
        if not is_cell(request.user):
            raise PermissionDenied()
        from apps.students.models import StudentProfile

        student = StudentProfile.objects.filter(pk=student_id, institution_id=drive.institution_id).first()
        if student is None:
            raise NotFound()
        return Response(evaluation_payload(drive, student, refresh=False))

    @extend_schema(
        parameters=[
            OpenApiParameter("eligible", bool),
            OpenApiParameter("registered", bool),
            OpenApiParameter("min_compatibility", float),
            OpenApiParameter("q", str),
        ],
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """Excel sheet of this drive's match results with the same filters as GET match.
        Eligibility and compatibility/readiness stay in separate columns. Audited."""
        from apps.core.excel import workbook_response
        from apps.core.services import record_audit

        drive = self.get_object()
        if not is_cell(request.user):
            raise PermissionDenied()
        rows = _match_rows(drive, request.query_params)["results"]
        gaps = {}
        for student_id, skill, impact in (
            GapItem.objects.filter(analysis__drive=drive, analysis__student_id__in=[r["student_id"] for r in rows])
            .order_by("analysis__student_id", "rank")
            .values_list("analysis__student_id", "skill__name", "impact")
        ):
            gaps.setdefault(student_id, []).append(f"{skill} ({impact})")
        columns = [
            ("Registration number", "roll_number"),
            ("Name", "name"),
            ("Department", "department"),
            ("CGPA", "cgpa"),
            (
                "Eligibility",
                lambda r: "—" if r["eligible"] is None else ("Eligible" if r["eligible"] else "Not eligible"),
            ),
            ("Failed criteria", "failed_criteria"),
            ("Compatibility %", "compatibility"),
            ("Readiness %", "readiness"),
            ("Registration status", lambda r: r["registration_status"] or "Not registered"),
            ("Top gaps (ranked)", lambda r: gaps.get(r["student_id"], [])[:5]),
        ]
        record_audit(
            actor=request.user,
            action="drive.export",
            target=drive,
            request=request,
            after={"rows": len(rows), "filters": dict(request.query_params.items())},
        )
        name = f"{drive.company.name}-{drive.role_title}".lower().replace(" ", "-")
        return workbook_response(name[:60], [("Match results", columns, rows)])

    @action(detail=True, methods=["get"])
    def registrations(self, request, pk=None):
        drive = self.get_object()
        if not is_cell(request.user):
            raise PermissionDenied()
        return Response(_match_rows(drive, {"registered": "true", **request.query_params.dict()}))

    @extend_schema(request=DecisionInput)
    @action(detail=True, methods=["post"], url_path=r"registrations/(?P<registration_id>\d+)/decide")
    def decide(self, request, pk=None, registration_id=None):
        drive = self.get_object()
        if not is_cell(request.user):
            raise PermissionDenied()
        registration = (
            Registration.objects.filter(pk=registration_id, drive=drive)
            .select_related("student__user", "drive__company")
            .first()
        )
        if registration is None:
            raise NotFound()
        data = DecisionInput(data=request.data)
        data.is_valid(raise_exception=True)
        _drive_error(
            services.decide_registration,
            registration,
            data.validated_data["status"],
            actor=request.user,
            request=request,
        )
        return Response({"id": registration.pk, "status": registration.status})

    # --- student ----------------------------------------------------------------------------

    def _student(self):
        student = student_for_user(self.request.user)
        if student is None:
            raise PermissionDenied("Only students can do this.")
        return student

    @extend_schema(parameters=[OpenApiParameter("refresh", bool)])
    @action(detail=True, methods=["get"], url_path="my-evaluation")
    def my_evaluation(self, request, pk=None):
        drive = self.get_object()
        student = self._student()
        return Response(evaluation_payload(drive, student, refresh=request.query_params.get("refresh") == "true"))

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        drive = self.get_object()
        registration = _drive_error(services.register, drive, self._student())
        return Response({"id": registration.pk, "status": registration.status}, status=status.HTTP_201_CREATED)

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        drive = self.get_object()
        registration = _drive_error(services.withdraw, drive, self._student())
        return Response({"id": registration.pk, "status": registration.status})


def _bool(value):
    return str(value).lower() in ("1", "true", "yes")


def _match_rows(drive, params):
    results = {m.student_id: m for m in matching_services.results_for_drive(drive)}
    eligibility = {e.student_id: e for e in EligibilityResult.objects.filter(drive=drive)}
    registrations = {r.student_id: r for r in Registration.objects.filter(drive=drive)}
    rows = []
    for student_id, m in results.items():
        e = eligibility.get(student_id)
        r = registrations.get(student_id)
        s = m.student
        rows.append(
            {
                "student_id": student_id,
                "name": s.name,
                "roll_number": s.roll_number,
                "department": s.department.code,
                "cgpa": str(s.cgpa),
                "eligible": e.is_eligible if e else None,
                "failed_criteria": [x["message"] for x in (e.reasons if e else []) if not x["passed"]],
                "compatibility": float(m.compatibility),
                "readiness": float(m.readiness_overall) if m.readiness_overall is not None else None,
                "registration_id": r.pk if r else None,
                "registration_status": r.status if r else None,
            }
        )
    if "eligible" in params and params["eligible"] != "":
        rows = [x for x in rows if x["eligible"] is _bool(params["eligible"])]
    if _bool(params.get("registered", "")):
        rows = [
            x for x in rows if x["registration_status"] and x["registration_status"] != RegistrationStatus.WITHDRAWN
        ]
    if params.get("min_compatibility"):
        try:
            threshold = float(params["min_compatibility"])
            rows = [x for x in rows if x["compatibility"] >= threshold]
        except ValueError:
            pass
    if q := params.get("q"):
        q = q.lower()
        rows = [x for x in rows if q in x["name"].lower() or q in x["roll_number"].lower()]
    rows.sort(key=lambda x: (-x["compatibility"], x["name"]))
    config = active_config(drive.institution_id)
    return {
        "drive_id": drive.pk,
        "last_matched_at": drive.last_matched_at,
        "ready_threshold": config.ready_threshold,
        "summary": {
            "evaluated": len(results),
            "eligible": sum(1 for e in eligibility.values() if e.is_eligible),
            "high_match": sum(1 for m in results.values() if float(m.compatibility) >= 70),
            "average_compatibility": round(sum(float(m.compatibility) for m in results.values()) / len(results), 1)
            if results
            else None,
            "registered": sum(1 for r in registrations.values() if r.status != RegistrationStatus.WITHDRAWN),
        },
        "results": rows,
    }


def _is_stale(result, drive, student):
    if result is None:
        return True
    latest_claim = SkillClaim.objects.filter(student=student).aggregate(t=Max("created_at"))["t"]
    latest_req = drive.requirements.aggregate(t=Max("updated_at"))["t"]
    latest_rule = drive.eligibility_rules.aggregate(t=Max("updated_at"))["t"]
    marks = [t for t in (latest_claim, latest_req, latest_rule, drive.updated_at) if t is not None]
    return any(t > result.computed_at for t in marks)


def evaluation_payload(drive, student, *, refresh):
    """Eligibility and readiness for one student and drive, deliberately as separate blocks."""
    result = MatchResult.objects.filter(drive=drive, student=student).first()
    if refresh or _is_stale(result, drive, student):
        matching_services.match_student(drive, student)
        result = MatchResult.objects.get(drive=drive, student=student)
    eligibility = EligibilityResult.objects.get(drive=drive, student=student)
    snapshot = ReadinessSnapshot.objects.filter(student=student, drive=drive).first()
    analysis = GapAnalysis.objects.filter(drive=drive, student=student).first()
    gaps = list(GapItem.objects.filter(analysis=analysis).select_related("skill__cluster")) if analysis else []
    registration = Registration.objects.filter(drive=drive, student=student).first()
    plan = PreparationPlan.objects.filter(student=student, drive=drive, status=PlanStatus.ACTIVE).first()
    config = active_config(drive.institution_id)
    return {
        "drive_id": drive.pk,
        "academic_record_verified": student.academic_record_verified,
        "eligibility": {
            "is_eligible": eligibility.is_eligible,
            "reasons": eligibility.reasons,
            "computed_at": eligibility.computed_at,
        },
        "compatibility": {
            "score": float(result.compatibility),
            "requirements": [
                {
                    **r,
                    "required_label": Level(r["required_level"]).label,
                    "level_label": Level(r["level"]).label,
                    "verified_label": Level(r["verified_level"]).label,
                }
                for r in result.breakdown
            ],
            "computed_at": result.computed_at,
        },
        "readiness": snapshot_data(snapshot) if snapshot else None,
        "is_ready": bool(snapshot and float(snapshot.overall) >= config.ready_threshold),
        "ready_threshold": config.ready_threshold,
        "gaps": [
            {
                "rank": g.rank,
                "skill_id": g.skill_id,
                "skill": g.skill.name,
                "cluster": g.skill.cluster.slug if g.skill.cluster else None,
                "kind": g.kind,
                "kind_label": g.get_kind_display(),
                "current": Level(g.current_level).label,
                "verified": Level(g.verified_level).label,
                "required": Level(g.required_level).label,
                "is_mandatory": g.is_mandatory,
                "impact": g.impact,
                "impact_score": float(g.impact_score),
                "suggested_action": g.suggested_action,
            }
            for g in gaps
        ],
        "registration": {"id": registration.pk, "status": registration.status} if registration else None,
        "registration_open": services.registration_open(drive),
        "plan_id": plan.pk if plan else None,
    }
