from django.conf import settings
from django.db.models import Prefetch, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import roles_required
from apps.accounts.roles import Role, has_role
from apps.core.api import service_call
from apps.core.services import record_audit
from apps.profiles.models import ClaimEvidence, SkillClaim
from apps.profiles.services import profile_completion
from apps.readiness.models import ReadinessSnapshot
from apps.readiness.services import active_config
from apps.students import selectors, services
from apps.students.models import Department, StudentProfile
from apps.students.validators import validate_registration_number
from apps.taxonomy.models import Level

STAFF = (Role.FACULTY, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN)
CELL = (Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN)


def resolve_student(request, student_id):
    """'me' or an id; returns 404 for anything the user may not see (no existence leak)."""
    if student_id == "me":
        student = selectors.student_for_user(request.user)
    else:
        try:
            pk = int(student_id)
        except (TypeError, ValueError):
            raise NotFound() from None
        student = selectors.visible_students(request.user).filter(pk=pk).first()
    if student is None:
        raise NotFound()
    return student


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]


class MentorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class StudentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    department = DepartmentSerializer(read_only=True)
    mentor = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "name",
            "email",
            "roll_number",
            "department",
            "graduation_year",
            "cgpa",
            "active_backlogs",
            "academic_record_verified",
            "mentor",
            "headline",
            "github_url",
            "linkedin_url",
            "onboarding_completed_at",
            "coding_activity",
            "has_resume",
        ]

    coding_activity = serializers.SerializerMethodField()
    has_resume = serializers.SerializerMethodField()

    def get_coding_activity(self, obj) -> float | None:
        cache = self.context.get("coding")
        if cache is None:
            from apps.coding.services import coding_activity

            cache = coding_activity([obj.pk])
        return cache.get(obj.pk, (None, []))[0]

    def get_has_resume(self, obj) -> bool:
        cache = self.context.get("resumes")
        if cache is not None:
            return obj.pk in cache
        return obj.resumes.filter(is_current=True).exists()

    @extend_schema_field(MentorSerializer(allow_null=True))
    def get_mentor(self, obj):
        if obj.mentor_id is None:
            return None
        return {"id": obj.mentor_id, "name": obj.mentor.get_full_name() or obj.mentor.email}


class StudentCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, allow_blank=True)
    roll_number = serializers.CharField(max_length=8, validators=[validate_registration_number])
    department_id = serializers.IntegerField()
    graduation_year = serializers.IntegerField(min_value=2000, max_value=2100)
    cgpa = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10)
    active_backlogs = serializers.IntegerField(min_value=0, default=0)
    mentor_id = serializers.IntegerField(required=False, allow_null=True)
    password = serializers.CharField(required=False, write_only=True, min_length=8)


class StudentStaffUpdateSerializer(serializers.Serializer):
    academic_record_verified = serializers.BooleanField(required=False)
    roll_number = serializers.CharField(max_length=8, validators=[validate_registration_number], required=False)
    department_id = serializers.IntegerField(required=False)
    graduation_year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    cgpa = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10, required=False)
    active_backlogs = serializers.IntegerField(min_value=0, required=False)
    mentor_id = serializers.IntegerField(required=False, allow_null=True)


class StudentSelfUpdateSerializer(serializers.Serializer):
    headline = serializers.CharField(max_length=160, required=False, allow_blank=True)
    github_url = serializers.URLField(required=False, allow_blank=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)


class FacultySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()


def _department(request, pk):
    dept = Department.objects.filter(pk=pk, institution_id=request.user.institution_id).first()
    if dept is None:
        raise serializers.ValidationError({"department_id": "Unknown department."})
    return dept


def _mentor(request, pk):
    if pk is None:
        return None
    from django.contrib.auth import get_user_model

    mentor = get_user_model().objects.filter(pk=pk, institution_id=request.user.institution_id).first()
    if mentor is None or not has_role(mentor, Role.FACULTY):
        raise serializers.ValidationError({"mentor_id": "Unknown faculty member."})
    return mentor


def filter_students(qs, params):
    if q := params.get("q"):
        qs = qs.filter(
            Q(roll_number__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
        )
    if dept := params.get("department"):
        qs = qs.filter(department__code__iexact=dept)
    if year := params.get("graduation_year"):
        try:
            qs = qs.filter(graduation_year=int(year))
        except ValueError:
            qs = qs.none()
    return qs.order_by("roll_number")


class StudentListView(ListAPIView):
    serializer_class = StudentSerializer
    permission_classes = [roles_required(*STAFF)]

    def get_queryset(self):
        return filter_students(selectors.visible_students(self.request.user), self.request.query_params)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        page = getattr(self, "_page_ids", None)
        if page is not None:
            from apps.coding.services import coding_activity
            from apps.students.models import StudentResume

            context["coding"] = coding_activity(page)
            context["resumes"] = set(
                StudentResume.objects.filter(student_id__in=page, is_current=True).values_list("student_id", flat=True)
            )
        return context

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)
        if page is not None:
            self._page_ids = [s.pk for s in page]
        return page

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str),
            OpenApiParameter("department", str),
            OpenApiParameter("graduation_year", int),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=StudentCreateSerializer, responses={201: StudentSerializer})
    def post(self, request):
        if not has_role(request.user, *CELL):
            raise PermissionDenied()
        data = StudentCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        student = service_call(
            services.create_student,
            error_types=(services.StudentError,),
            institution=request.user.institution,
            email=v["email"],
            first_name=v["first_name"],
            last_name=v["last_name"],
            roll_number=v["roll_number"],
            department=_department(request, v["department_id"]),
            graduation_year=v["graduation_year"],
            cgpa=v["cgpa"],
            active_backlogs=v["active_backlogs"],
            mentor=_mentor(request, v.get("mentor_id")),
            password=v.get("password"),
        )
        record_audit(actor=request.user, action="student.create", target=student, request=request)
        return Response(StudentSerializer(student).data, status=status.HTTP_201_CREATED)


class StudentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StudentSerializer)
    def get(self, request, student_id):
        return Response(StudentSerializer(resolve_student(request, student_id)).data)

    @extend_schema(request=StudentStaffUpdateSerializer, responses=StudentSerializer)
    def patch(self, request, student_id):
        student = resolve_student(request, student_id)
        if student.user_id == request.user.pk:
            data = StudentSelfUpdateSerializer(data=request.data, partial=True)
            data.is_valid(raise_exception=True)
            changes, by_staff = dict(data.validated_data), False
        elif has_role(request.user, *CELL):
            data = StudentStaffUpdateSerializer(data=request.data, partial=True)
            data.is_valid(raise_exception=True)
            changes, by_staff = dict(data.validated_data), True
            if "department_id" in changes:
                changes["department"] = _department(request, changes.pop("department_id"))
            if "mentor_id" in changes:
                changes["mentor"] = _mentor(request, changes.pop("mentor_id"))
        else:
            raise PermissionDenied()
        before = {k: str(getattr(student, k)) for k in changes}
        service_call(
            services.update_student, student, by_staff=by_staff, error_types=(services.StudentError,), **changes
        )
        record_audit(
            actor=request.user,
            action="student.update",
            target=student,
            request=request,
            before=before,
            after={k: str(getattr(student, k)) for k in changes},
        )
        return Response(StudentSerializer(student).data)


class SkillProfileView(APIView):
    """GET /students/:id/profile — levelled skill claims with the evidence behind each."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, student_id):
        student = resolve_student(request, student_id)
        claims = (
            SkillClaim.objects.filter(student=student)
            .select_related("skill__cluster")
            .prefetch_related(Prefetch("supports", queryset=ClaimEvidence.objects.select_related("evidence")))
            .order_by("-level", "skill__name")
        )
        return Response(
            {
                "student": StudentSerializer(student).data,
                "completion": profile_completion(student),
                "claims": [
                    {
                        "skill_id": c.skill_id,
                        "skill": c.skill.name,
                        "cluster_slug": c.skill.cluster.slug if c.skill.cluster else None,
                        "cluster": c.skill.cluster.name if c.skill.cluster else None,
                        "level": c.level,
                        "level_label": Level(c.level).label,
                        "verified_level": c.verified_level,
                        "verified_level_label": Level(c.verified_level).label,
                        "is_verified": c.is_verified,
                        "evidence": [
                            {
                                "id": s.evidence_id,
                                "title": s.evidence.title,
                                "source_type": s.evidence.source_type,
                                "source_label": s.evidence.get_source_type_display(),
                                "verification_status": s.evidence.verification_status,
                                "claimed_level": Level(s.claimed_level).label,
                                "effective_level": Level(s.effective_level).label,
                                "verified": s.verified,
                            }
                            for s in c.supports.all()
                        ],
                    }
                    for c in claims
                ],
            }
        )


class ReadinessView(APIView):
    """GET /students/:id/readiness — latest general snapshot, its explanation, and history."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, student_id):
        student = resolve_student(request, student_id)
        latest = ReadinessSnapshot.objects.filter(student=student, drive__isnull=True).first()
        history = ReadinessSnapshot.objects.filter(student=student, drive__isnull=True).order_by("-created_at")[:20]
        config = active_config(student.institution_id)
        return Response(
            {
                "latest": snapshot_data(latest) if latest else None,
                "ready_threshold": config.ready_threshold,
                "history": [{"at": s.created_at, "overall": float(s.overall)} for s in reversed(list(history))],
            }
        )


class StudentDrivesView(APIView):
    """GET /students/:id/drives — the drives a student registered for, with eligibility and
    compatibility/readiness reported as separate fields, plus plan progress. Visible to the
    student, their mentor and the placement cell."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, student_id):
        from apps.drives.models import EligibilityResult, Registration
        from apps.matching.models import MatchResult
        from apps.planning.models import ItemStatus, PlanStatus, PreparationPlan

        student = resolve_student(request, student_id)
        registrations = list(
            Registration.objects.filter(student=student).select_related("drive__company").order_by("-registered_at")
        )
        drive_ids = [r.drive_id for r in registrations]
        eligibility = {e.drive_id: e for e in EligibilityResult.objects.filter(student=student, drive_id__in=drive_ids)}
        matches = {m.drive_id: m for m in MatchResult.objects.filter(student=student, drive_id__in=drive_ids)}
        plans = {
            p.drive_id: p
            for p in PreparationPlan.objects.filter(
                student=student, drive_id__in=drive_ids, status=PlanStatus.ACTIVE
            ).prefetch_related("items")
        }
        rows = []
        for r in registrations:
            e, m, p = eligibility.get(r.drive_id), matches.get(r.drive_id), plans.get(r.drive_id)
            items = list(p.items.all()) if p else []
            rows.append(
                {
                    "drive_id": r.drive_id,
                    "company": r.drive.company.name,
                    "role": r.drive.role_title,
                    "drive_date": r.drive.drive_date,
                    "drive_status": r.drive.status,
                    "registration_status": r.status,
                    "registered_at": r.registered_at,
                    "is_eligible": e.is_eligible if e else None,
                    "failed_rules": [x for x in e.reasons if not x.get("passed")] if e else [],
                    "compatibility": float(m.compatibility) if m else None,
                    "readiness": float(m.readiness_overall) if m and m.readiness_overall is not None else None,
                    "plan": {
                        "id": p.pk,
                        "done": sum(1 for i in items if i.status == ItemStatus.DONE),
                        "total": len(items),
                    }
                    if p
                    else None,
                }
            )
        return Response(rows)


def snapshot_data(snap):
    return {
        "id": snap.pk,
        "drive_id": snap.drive_id,
        "created_at": snap.created_at,
        "config_version": snap.config.version,
        "overall": float(snap.overall),
        "technical": float(snap.technical),
        "aptitude": float(snap.aptitude),
        "communication": float(snap.communication),
        "project_depth": float(snap.project_depth),
        "coding_activity": float(snap.coding_activity),
        "explanation": snap.explanation,
    }


class DepartmentListView(ListAPIView):
    serializer_class = DepartmentSerializer
    pagination_class = None

    def get_queryset(self):
        return Department.objects.filter(institution_id=self.request.user.institution_id)

    @extend_schema(request=DepartmentSerializer, responses={201: DepartmentSerializer})
    def post(self, request):
        if not has_role(request.user, *CELL):
            raise PermissionDenied()
        data = DepartmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        code = data.validated_data["code"].strip().upper()
        if Department.objects.filter(institution_id=request.user.institution_id, code=code).exists():
            raise serializers.ValidationError({"code": "Department code already exists."})
        dept = Department.objects.create(
            institution_id=request.user.institution_id, code=code, name=data.validated_data["name"]
        )
        return Response(DepartmentSerializer(dept).data, status=status.HTTP_201_CREATED)


class FacultyListView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=FacultySerializer(many=True))
    def get(self, request):
        from django.contrib.auth import get_user_model

        users = (
            get_user_model()
            .objects.filter(institution_id=request.user.institution_id, groups__name=Role.FACULTY)
            .order_by("first_name", "email")
        )
        return Response([{"id": u.pk, "name": u.get_full_name() or u.email, "email": u.email} for u in users])


class OnboardingView(APIView):
    """Student first-run: whether the profile pop-up should show, and marking it done."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        student = selectors.student_for_user(request.user)
        if student is None:
            return Response({"required": False})
        from apps.coding.models import CodingProfile

        platforms = set(CodingProfile.objects.filter(student=student).values_list("platform", flat=True))
        return Response(
            {
                "required": student.onboarding_completed_at is None,
                "github": "github" in platforms,
                "leetcode": "leetcode" in platforms,
                "linkedin": bool(student.linkedin_url),
                "resume": services.current_resume(student) is not None,
            }
        )

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        student = selectors.student_for_user(request.user)
        if student is None:
            raise PermissionDenied()
        services.complete_onboarding(student)
        return Response({"required": False})


def _resume_payload(resume):
    from apps.students.resumes import signed_url

    return {
        "id": resume.pk,
        "name": resume.original_name,
        "size": resume.size,
        "uploaded_at": resume.created_at,
        "url": signed_url(resume.file.name),
        "expires_in": settings.RESUME_URL_EXPIRY_SECONDS,
    }


class ResumeView(APIView):
    """GET /students/:id/resume — signed view link for the current resume (self, mentor, placement cell).
    POST (self, multipart `file`) — upload a PDF. DELETE (self) — remove all versions."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, student_id):
        student = resolve_student(request, student_id)
        resume = services.current_resume(student)
        if resume is None:
            return Response({"detail": "No resume uploaded."}, status=status.HTTP_404_NOT_FOUND)
        if student.user_id != request.user.pk:
            record_audit(actor=request.user, action="student.resume.view", target=resume, request=request)
        response = Response(_resume_payload(resume))
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(
        request={
            "multipart/form-data": {"type": "object", "properties": {"file": {"type": "string", "format": "binary"}}}
        },
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request, student_id):
        student = resolve_student(request, student_id)
        if student.user_id != request.user.pk:
            raise PermissionDenied("Students upload their own resume.")
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"detail": "Choose a PDF to upload."}, status=status.HTTP_400_BAD_REQUEST)
        from apps.students.resumes import ResumeError

        try:
            resume = services.upload_resume(student, uploaded, uploaded_by=request.user)
        except ResumeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_resume_payload(resume), status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def delete(self, request, student_id):
        student = resolve_student(request, student_id)
        if student.user_id != request.user.pk:
            raise PermissionDenied("Students manage their own resume.")
        services.delete_resume(student, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


EXPORT_PARAMS = [
    OpenApiParameter("q", str),
    OpenApiParameter("department", str),
    OpenApiParameter("graduation_year", int),
    OpenApiParameter("band", str, description="Readiness band: 80-100, 60-80, 40-60, 0-40 or none"),
    OpenApiParameter("academic_verified", bool),
]
STUDENT_COLUMNS = [
    ("Registration number", "roll_number"),
    ("Name", "name"),
    ("Email", "email"),
    ("Department", "department"),
    ("Graduation year", "graduation_year"),
    ("CGPA", "cgpa"),
    ("Active backlogs", "active_backlogs"),
    ("Academics confirmed", "academic_record_verified"),
    ("Mentor", "mentor"),
    ("Readiness % (general)", "readiness"),
    ("Evidence items", "evidence_total"),
    ("Verified evidence", "evidence_verified"),
    ("Pending verification", "evidence_pending"),
    ("Rejected evidence", "evidence_rejected"),
    ("Drives registered", "registrations"),
    ("Eligible for active drives", "eligible_drives"),
    ("Plan tasks done", "plan_done"),
    ("Plan tasks total", "plan_total"),
]


def _in_band(readiness, band):
    if band == "none":
        return readiness is None
    try:
        low, high = (float(x) for x in band.split("-"))
    except ValueError:
        return True
    return readiness is not None and low <= readiness < (high if high < 100 else 101)


class StudentExportView(APIView):
    """GET /students/export — Excel sheet of the students the user can see (placement cell: the
    institution; faculty: their mentees), with the same filters as the list plus readiness band.
    Each export is audited. Not available to recruiters."""

    permission_classes = [roles_required(*STAFF)]

    @extend_schema(parameters=EXPORT_PARAMS, responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request):
        from apps.core.excel import workbook_response
        from apps.reporting.services import student_summaries

        params = request.query_params
        qs = filter_students(selectors.visible_students(request.user), params)
        if "academic_verified" in params:
            qs = qs.filter(academic_record_verified=params["academic_verified"].lower() in ("1", "true", "yes"))
        rows = student_summaries(qs)
        if band := params.get("band"):
            rows = [r for r in rows if _in_band(r["readiness"], band)]
        record_audit(
            actor=request.user,
            action="students.export",
            request=request,
            after={"rows": len(rows), "filters": {k: v for k, v in params.items()}},
        )
        return workbook_response("students", [("Students", STUDENT_COLUMNS, rows)])


class StudentImportView(APIView):
    """Placement cell bulk import. GET — blank template. POST (multipart `file`, optional
    `dry_run=true`) — validate every row; apply only if all rows are valid."""

    permission_classes = [roles_required(*CELL)]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request):
        from apps.core.excel import workbook_response
        from apps.students.importing import COLUMNS, EXAMPLE

        # The Students sheet is left empty on purpose: an example row there could match a real
        # registration number and overwrite that student if the template were imported as is.
        return workbook_response(
            "student-import-template",
            [
                ("Students", [(c, c) for c, _ in COLUMNS], []),
                (
                    "Instructions",
                    [("Column", "c"), ("Notes", "n"), ("Example", "e")],
                    [{"c": c, "n": n, "e": EXAMPLE.get(c, "")} for c, n in COLUMNS],
                ),
            ],
        )

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}, "dry_run": {"type": "boolean"}},
            }
        },
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request):
        from apps.core.excel import ExcelError
        from apps.students.importing import import_students

        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"detail": "Choose an .xlsx file to import."}, status=status.HTTP_400_BAD_REQUEST)
        dry_run = str(request.data.get("dry_run", "")).lower() in ("1", "true", "yes")
        try:
            result = import_students(request.user.institution, uploaded, actor=request.user, dry_run=dry_run)
        except ExcelError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)
