from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from apps.accounts.roles import Role, has_role
from apps.assessments import services
from apps.assessments.models import Assessment, AssessmentKind, MockInterview, Rubric, RubricCriterion
from apps.core.api import service_call
from apps.students.selectors import visible_students
from apps.taxonomy.models import POSITIVE_LEVEL_CHOICES, Level, Skill

ASSESSORS = (Role.FACULTY, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD)
RUBRIC_EDITORS = (Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN)


class CriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricCriterion
        fields = ["id", "name", "description", "max_score", "order"]


class RubricSerializer(serializers.ModelSerializer):
    criteria = CriterionSerializer(many=True)

    class Meta:
        model = Rubric
        fields = ["id", "name", "kind", "description", "is_active", "criteria"]


class AssessmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    rubric = serializers.CharField(source="rubric.name", read_only=True)
    skill = serializers.CharField(source="skill.name", read_only=True, default=None)
    assessed_by = serializers.SerializerMethodField()
    scores = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "student_id",
            "student_name",
            "kind",
            "title",
            "rubric",
            "skill",
            "assessed_on",
            "total_score",
            "max_score",
            "percentage",
            "notes",
            "assessed_by",
            "scores",
        ]

    def get_assessed_by(self, obj) -> str:
        return obj.assessed_by.get_full_name() or obj.assessed_by.email

    def get_scores(self, obj) -> list[dict]:
        return [
            {"criterion": s.criterion.name, "score": float(s.score), "max": s.criterion.max_score}
            for s in obj.scores.all()
        ]


class MockInterviewSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    interviewer = serializers.SerializerMethodField()
    skill_ratings = serializers.SerializerMethodField()

    class Meta:
        model = MockInterview
        fields = [
            "id",
            "student_id",
            "student_name",
            "interviewer",
            "conducted_on",
            "role_focus",
            "technical_score",
            "communication_score",
            "problem_solving_score",
            "feedback",
            "skill_ratings",
        ]

    def get_interviewer(self, obj) -> str:
        return obj.interviewer.get_full_name() or obj.interviewer.email

    def get_skill_ratings(self, obj) -> list[dict]:
        return [{"skill": r.skill.name, "level": Level(r.level).label} for r in obj.skill_ratings.all()]


class ScoreInput(serializers.Serializer):
    criterion_id = serializers.IntegerField()
    score = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0)


class AssessmentInput(serializers.Serializer):
    student_id = serializers.IntegerField()
    rubric_id = serializers.IntegerField()
    title = serializers.CharField(max_length=200)
    skill_id = serializers.IntegerField(required=False, allow_null=True)
    assessed_on = serializers.DateField()
    scores = ScoreInput(many=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class RatingInput(serializers.Serializer):
    skill_id = serializers.IntegerField()
    level = serializers.ChoiceField(choices=POSITIVE_LEVEL_CHOICES)


class MockInterviewInput(serializers.Serializer):
    student_id = serializers.IntegerField()
    conducted_on = serializers.DateField()
    role_focus = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    technical_score = serializers.IntegerField(min_value=0, max_value=100)
    communication_score = serializers.IntegerField(min_value=0, max_value=100)
    problem_solving_score = serializers.IntegerField(min_value=0, max_value=100)
    feedback = serializers.CharField(required=False, allow_blank=True, default="")
    skill_ratings = RatingInput(many=True, required=False, default=list)


class RubricInput(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=AssessmentKind.choices)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    criteria = CriterionSerializer(many=True)


def _student(request, pk):
    student = visible_students(request.user).filter(pk=pk).first()
    if student is None:
        raise NotFound("Student not found.")
    return student


def _skill(request, pk):
    if pk is None:
        return None
    skill = Skill.objects.filter(pk=pk, institution_id=request.user.institution_id, is_active=True).first()
    if skill is None:
        raise serializers.ValidationError({"skill_id": "Unknown skill."})
    return skill


class RubricListView(ListAPIView):
    serializer_class = RubricSerializer
    pagination_class = None

    def get_queryset(self):
        return Rubric.objects.filter(institution_id=self.request.user.institution_id, is_active=True).prefetch_related(
            "criteria"
        )

    @extend_schema(request=RubricInput, responses={201: RubricSerializer})
    def post(self, request):
        if not has_role(request.user, *RUBRIC_EDITORS):
            raise PermissionDenied()
        data = RubricInput(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        if not v["criteria"]:
            raise serializers.ValidationError({"criteria": "Add at least one criterion."})
        rubric = Rubric.objects.create(
            institution_id=request.user.institution_id, name=v["name"], kind=v["kind"], description=v["description"]
        )
        RubricCriterion.objects.bulk_create(
            RubricCriterion(rubric=rubric, order=i, **c) for i, c in enumerate(v["criteria"])
        )
        return Response(RubricSerializer(rubric).data, status=status.HTTP_201_CREATED)


class AssessmentListView(ListAPIView):
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        qs = (
            Assessment.objects.filter(student__in=visible_students(self.request.user))
            .select_related("student__user", "rubric", "skill", "assessed_by")
            .prefetch_related("scores__criterion")
        )
        if student := self.request.query_params.get("student"):
            qs = qs.filter(student_id=student)
        return qs

    @extend_schema(parameters=[OpenApiParameter("student", int)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=AssessmentInput, responses={201: AssessmentSerializer})
    def post(self, request):
        if not has_role(request.user, *ASSESSORS):
            raise PermissionDenied()
        data = AssessmentInput(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        student = _student(request, v["student_id"])
        rubric = Rubric.objects.filter(pk=v["rubric_id"], institution_id=request.user.institution_id).first()
        if rubric is None:
            raise serializers.ValidationError({"rubric_id": "Unknown rubric."})
        criteria = {c.pk: c for c in rubric.criteria.all()}
        try:
            scores = {criteria[s["criterion_id"]]: s["score"] for s in v["scores"]}
        except KeyError:
            raise serializers.ValidationError({"scores": "Criterion does not belong to this rubric."}) from None
        assessment = service_call(
            services.record_assessment,
            student=student,
            rubric=rubric,
            title=v["title"],
            assessed_by=request.user,
            assessed_on=v["assessed_on"],
            scores=scores,
            skill=_skill(request, v.get("skill_id")),
            notes=v["notes"],
            request=request,
            error_types=(services.AssessmentError,),
        )
        return Response(AssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)


class MockInterviewListView(ListAPIView):
    serializer_class = MockInterviewSerializer

    def get_queryset(self):
        qs = (
            MockInterview.objects.filter(student__in=visible_students(self.request.user))
            .select_related("student__user", "interviewer")
            .prefetch_related("skill_ratings__skill")
        )
        if student := self.request.query_params.get("student"):
            qs = qs.filter(student_id=student)
        return qs

    @extend_schema(parameters=[OpenApiParameter("student", int)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=MockInterviewInput, responses={201: MockInterviewSerializer})
    def post(self, request):
        if not has_role(request.user, *ASSESSORS):
            raise PermissionDenied()
        data = MockInterviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        student = _student(request, v.pop("student_id"))
        ratings = [(_skill(request, r["skill_id"]), r["level"]) for r in v.pop("skill_ratings")]
        interview = service_call(
            services.record_mock_interview,
            student=student,
            interviewer=request.user,
            skill_ratings=ratings,
            request=request,
            error_types=(services.AssessmentError,),
            **v,
        )
        return Response(MockInterviewSerializer(interview).data, status=status.HTTP_201_CREATED)
