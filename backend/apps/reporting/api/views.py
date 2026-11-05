from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import roles_required
from apps.accounts.roles import Role
from apps.core.models import BackgroundJob
from apps.drives.api.views import JobSerializer, evaluation_payload
from apps.drives.models import ACTIVE_STATUSES, Drive, EligibilityResult
from apps.evidence.models import EvidenceItem, VerificationStatus
from apps.notifications.models import Notification
from apps.planning.models import ItemStatus, PlanItem, PlanStatus, PreparationPlan
from apps.profiles.models import SkillClaim
from apps.profiles.services import profile_completion
from apps.readiness.models import ReadinessSnapshot
from apps.reporting import services
from apps.students.selectors import student_for_user
from apps.taxonomy.models import Level
from apps.verification.services import pending_for_reviewer

CELL = (Role.PLACEMENT_OFFICER, Role.PLACEMENT_HEAD, Role.ADMIN)
INSTITUTIONAL = (Role.PLACEMENT_HEAD, Role.ADMIN)


def _drive(request, drive_id):
    drive = Drive.objects.filter(pk=drive_id, institution_id=request.user.institution_id).first()
    if drive is None:
        raise NotFound()
    return drive


class OverviewView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.overview(request.user.institution_id))


class SupplyDemandView(APIView):
    """Skill supply against drive demand (P06 §10: the most valuable report)."""

    permission_classes = [roles_required(*CELL)]

    @extend_schema(
        parameters=[OpenApiParameter("population", str, enum=["all", "eligible"])], responses=OpenApiTypes.OBJECT
    )
    def get(self, request, drive_id):
        population = request.query_params.get("population", "all")
        return Response(
            services.supply_demand_for_drive(
                _drive(request, drive_id), "eligible" if population == "eligible" else "all"
            )
        )


class DemandAcrossDrivesView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.demand_across_drives(request.user.institution_id))


class GapFrequencyView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(parameters=[OpenApiParameter("drive", int)], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        drive = _drive(request, request.query_params["drive"]) if request.query_params.get("drive") else None
        return Response(services.gap_frequency(request.user.institution_id, drive=drive))


class VerificationCoverageView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.verification_coverage(request.user.institution_id))


class FunnelView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, drive_id):
        return Response(services.drive_funnel(_drive(request, drive_id)))


class DepartmentComparisonView(APIView):
    permission_classes = [roles_required(*INSTITUTIONAL)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.department_comparison(request.user.institution_id))


class TrainingEffectivenessView(APIView):
    permission_classes = [roles_required(*INSTITUTIONAL)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(services.training_effectiveness(request.user.institution_id))


class BatchReadinessView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=JobSerializer(many=True))
    def get(self, request):
        jobs = BackgroundJob.objects.filter(institution_id=request.user.institution_id, kind="batch_readiness")[:10]
        return Response(JobSerializer(jobs, many=True).data)

    @extend_schema(request=None, responses={202: JobSerializer})
    def post(self, request):
        job = services.start_batch_readiness_job(request.user.institution_id, created_by=request.user)
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class JobView(APIView):
    permission_classes = [roles_required(*CELL)]

    @extend_schema(responses=JobSerializer)
    def get(self, request, job_id):
        job = BackgroundJob.objects.filter(pk=job_id, institution_id=request.user.institution_id).first()
        if job is None:
            raise NotFound()
        return Response(JobSerializer(job).data)


class StudentDashboardView(APIView):
    """Everything the student dashboard needs: 'Where do I stand?' (AGENTS.md §28)."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        student = student_for_user(request.user)
        if student is None:
            raise PermissionDenied("Only students have a student dashboard.")
        evidence = list(EvidenceItem.objects.filter(student=student).values_list("verification_status", flat=True))
        general = ReadinessSnapshot.objects.filter(student=student, drive__isnull=True).first()
        drives = []
        for drive in (
            Drive.objects.filter(institution_id=student.institution_id, status__in=ACTIVE_STATUSES)
            .select_related("company")
            .order_by("drive_date", "-created_at")[:8]
        ):
            ev = evaluation_payload(drive, student, refresh=False)
            drives.append(
                {
                    "id": drive.pk,
                    "company": drive.company.name,
                    "role": drive.role_title,
                    "drive_date": drive.drive_date,
                    "status": drive.status,
                    "is_eligible": ev["eligibility"]["is_eligible"],
                    "compatibility": ev["compatibility"]["score"],
                    "readiness": ev["readiness"]["overall"] if ev["readiness"] else None,
                    "is_ready": ev["is_ready"],
                    "registration": ev["registration"],
                    "top_gaps": ev["gaps"][:3],
                }
            )
        eligible = EligibilityResult.objects.filter(
            student=student, is_eligible=True, drive__status__in=ACTIVE_STATUSES
        ).count()
        claims = (
            SkillClaim.objects.filter(student=student)
            .select_related("skill__cluster")
            .order_by("-level", "skill__name")
        )
        today = timezone.localdate()
        # The nearest active plan drives the "next steps" list, its NEXT item and the time budget,
        # so all three describe the same tasks as the plan page.
        plan = (
            PreparationPlan.objects.filter(student=student, status=PlanStatus.ACTIVE)
            .select_related("drive__company")
            .annotate(total=Count("items"), done=Count("items", filter=Q(items__status=ItemStatus.DONE)))
            .order_by("end_date")
            .first()
        )
        tasks = (
            PlanItem.objects.filter(plan=plan)
            .exclude(status=ItemStatus.DONE)
            .select_related("skill__cluster", "plan")
            .order_by("due_date", "order")[:6]
            if plan
            else []
        )
        plan_target = (plan.drive.drive_date if plan and plan.drive and plan.drive.drive_date else None) or (
            plan.end_date if plan else None
        )
        activity = Notification.objects.filter(recipient=request.user)[:6]
        return Response(
            {
                "student": {
                    "name": student.name,
                    "roll_number": student.roll_number,
                    "department": student.department.code,
                },
                "cards": {
                    "profile_completion": profile_completion(student)["percent"],
                    "verified_evidence": sum(s == VerificationStatus.VERIFIED for s in evidence),
                    "total_evidence": len(evidence),
                    "eligible_drives": eligible,
                    "readiness": float(general.overall) if general else None,
                },
                "readiness": {
                    "overall": float(general.overall),
                    "technical": float(general.technical),
                    "aptitude": float(general.aptitude),
                    "communication": float(general.communication),
                    "project_depth": float(general.project_depth),
                    "coding_activity": float(general.coding_activity),
                }
                if general
                else None,
                "skills": [
                    {
                        "skill": c.skill.name,
                        "level": c.level,
                        "level_label": Level(c.level).label,
                        "percent": round(100 * c.level / Level.EXPERT),
                        "is_verified": c.is_verified,
                        "verified_level": c.verified_level,
                        "cluster": c.skill.cluster.slug if c.skill.cluster else None,
                    }
                    for c in claims[:10]
                ],
                "drives": drives,
                "tasks": [
                    {
                        "id": t.pk,
                        "title": t.title,
                        "due_date": t.due_date,
                        "is_checkpoint": t.is_checkpoint,
                        "overdue": t.due_date < today,
                        "status": t.status,
                        "skill": t.skill.name if t.skill else None,
                        "cluster": t.skill.cluster.slug if t.skill and t.skill.cluster else None,
                        "plan_id": t.plan_id,
                    }
                    for t in tasks
                ],
                # Time budget for the nearest active plan: days left before the drive vs work left.
                "plan": {
                    "id": plan.pk,
                    "title": plan.title,
                    "company": plan.drive.company.name if plan.drive else None,
                    "start_date": plan.start_date,
                    "end_date": plan.end_date,
                    "drive_date": plan.drive.drive_date if plan.drive else None,
                    "days_left": max(0, (plan_target - today).days),
                    "total_days": max(1, (plan_target - plan.start_date).days),
                    "total": plan.total,
                    "done": plan.done,
                }
                if plan
                else None,
                "activity": [{"title": n.title, "at": n.created_at, "link": n.link} for n in activity],
            }
        )


class FacultyDashboardView(APIView):
    permission_classes = [roles_required(Role.FACULTY)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.students.models import StudentProfile

        mentees = (
            StudentProfile.objects.filter(mentor=request.user, institution_id=request.user.institution_id)
            .select_related("user", "department", "mentor")
            .order_by("roll_number")
        )
        rows = services.student_summaries(mentees)
        pending = pending_for_reviewer(request.user)
        return Response(
            {
                "mentees": len(rows),
                "pending_verifications": pending.count(),
                # Lowest readiness first, so the mentor knows who to check in with.
                "students": sorted(rows, key=lambda x: (x["readiness"] is None, x["readiness"] or 0)),
            }
        )
