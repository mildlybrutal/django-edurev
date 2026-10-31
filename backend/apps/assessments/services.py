from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.accounts.roles import Role, has_role
from apps.core.services import record_audit
from apps.evidence import services as evidence_services
from apps.evidence.models import SourceType
from apps.taxonomy.models import Level

from .models import Assessment, AssessmentKind, AssessmentScore, MockInterview, MockInterviewSkillRating


class AssessmentError(ValueError):
    pass


def can_assess(user, student):
    """Faculty assess their mentees; the placement cell can assess any student of the institution."""
    if user.institution_id != student.institution_id or student.user_id == user.pk:
        return False
    if has_role(user, Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD):
        return True
    return has_role(user, Role.FACULTY) and student.mentor_id == user.pk


def percentage_to_level(pct):
    """Map an assessment percentage to a proficiency level. Implementation choice, documented in
    docs/scoring-policy.md: <40 Beginner, 40–69 Intermediate, 70–89 Advanced, >=90 Expert."""
    if pct >= 90:
        return Level.EXPERT
    if pct >= 70:
        return Level.ADVANCED
    if pct >= 40:
        return Level.INTERMEDIATE
    return Level.BEGINNER


@transaction.atomic
def record_assessment(*, student, rubric, title, assessed_by, assessed_on, scores, skill=None, notes="", request=None):
    """`scores` maps RubricCriterion -> score. Every criterion must be scored within its maximum."""
    if not can_assess(assessed_by, student):
        raise AssessmentError("You cannot record assessments for this student.")
    if rubric.institution_id != student.institution_id or not rubric.is_active:
        raise AssessmentError("Unknown rubric.")
    criteria = list(rubric.criteria.all())
    if not criteria:
        raise AssessmentError("This rubric has no criteria.")
    if {c.pk for c in scores} != {c.pk for c in criteria}:
        raise AssessmentError("Score every criterion of the rubric exactly once.")
    for criterion, score in scores.items():
        if score < 0 or score > criterion.max_score:
            raise AssessmentError(f"{criterion.name}: score must be between 0 and {criterion.max_score}.")
    if rubric.kind == AssessmentKind.TECHNICAL and skill is None:
        raise AssessmentError("Technical assessments must name the skill assessed.")
    if skill is not None and skill.institution_id != student.institution_id:
        raise AssessmentError("Unknown skill.")

    total = sum((Decimal(str(s)) for s in scores.values()), Decimal("0"))
    maximum = Decimal(sum(c.max_score for c in criteria))
    pct = (total * 100 / maximum).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    tags = [(skill, percentage_to_level(pct))] if skill is not None else []
    evidence = evidence_services.record_institutional_evidence(
        student=student,
        source_type=SourceType.ASSESSMENT,
        title=title,
        recorded_by=assessed_by,
        description=f"{rubric.get_kind_display()} assessment: {pct}%",
        tags=tags,
        extracted_data={"kind": rubric.kind, "percentage": float(pct)},
    )
    assessment = Assessment.objects.create(
        institution_id=student.institution_id,
        student=student,
        rubric=rubric,
        kind=rubric.kind,
        title=title,
        skill=skill,
        assessed_by=assessed_by,
        assessed_on=assessed_on,
        total_score=total,
        max_score=maximum,
        percentage=pct,
        notes=notes,
        evidence=evidence,
    )
    AssessmentScore.objects.bulk_create(
        AssessmentScore(assessment=assessment, criterion=c, score=Decimal(str(s))) for c, s in scores.items()
    )
    record_audit(
        actor=assessed_by,
        action="assessment.record",
        target=assessment,
        request=request,
        after={"percentage": float(pct)},
    )
    return assessment


@transaction.atomic
def record_mock_interview(
    *,
    student,
    interviewer,
    conducted_on,
    technical_score,
    communication_score,
    problem_solving_score,
    feedback="",
    role_focus="",
    skill_ratings=(),
    request=None,
):
    if not can_assess(interviewer, student):
        raise AssessmentError("You cannot record mock interviews for this student.")
    for name, value in (
        ("technical", technical_score),
        ("communication", communication_score),
        ("problem solving", problem_solving_score),
    ):
        if not 0 <= value <= 100:
            raise AssessmentError(f"The {name} score must be between 0 and 100.")
    for skill, level in skill_ratings:
        if skill.institution_id != student.institution_id:
            raise AssessmentError("Unknown skill.")
        if level not in Level.values or level == Level.NONE:
            raise AssessmentError("Skill ratings must be Beginner to Expert.")

    evidence = evidence_services.record_institutional_evidence(
        student=student,
        source_type=SourceType.MOCK_INTERVIEW,
        title=f"Mock interview{f' — {role_focus}' if role_focus else ''}",
        recorded_by=interviewer,
        description=feedback,
        tags=list(skill_ratings),
        extracted_data={
            "technical": technical_score,
            "communication": communication_score,
            "problem_solving": problem_solving_score,
        },
    )
    interview = MockInterview.objects.create(
        institution_id=student.institution_id,
        student=student,
        interviewer=interviewer,
        conducted_on=conducted_on,
        role_focus=role_focus,
        technical_score=technical_score,
        communication_score=communication_score,
        problem_solving_score=problem_solving_score,
        feedback=feedback,
        evidence=evidence,
    )
    MockInterviewSkillRating.objects.bulk_create(
        MockInterviewSkillRating(interview=interview, skill=skill, level=level) for skill, level in skill_ratings
    )
    record_audit(actor=interviewer, action="mock_interview.record", target=interview, request=request)
    return interview
