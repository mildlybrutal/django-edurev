from collections import Counter

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.api.serializers import MeSerializer
from apps.accounts.api.views import LoginView, LogoutView, MFAVerifyView, RefreshView
from apps.accounts.authentication import RecruiterCookieJWTAuthentication
from apps.accounts.portals import Portal
from apps.accounts.roles import Role, has_role
from apps.matching.models import MatchResult
from apps.profiles.models import SkillClaim
from apps.recruiter import services
from apps.recruiter.models import AccessAction
from apps.reporting.services import band_of
from apps.taxonomy.models import SkillClosure
from apps.taxonomy.selectors import search_skills

from .candidates import load_context, released_fields, serialize_candidate


class RecruiterLoginView(LoginView):
    portal = Portal.RECRUITER
    throttle_scope = "recruiter_login"


class RecruiterMFAVerifyView(MFAVerifyView):
    portal = Portal.RECRUITER
    throttle_scope = "recruiter_login"


class RecruiterRefreshView(RefreshView):
    portal = Portal.RECRUITER


class RecruiterLogoutView(LogoutView):
    portal = Portal.RECRUITER


class IsRecruiter(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and has_role(request.user, Role.RECRUITER))


class RecruiterAPIView(APIView):
    """Base for recruiter endpoints: recruiter-portal token only, recruiter role, recruiter
    throttle scope, never cached."""

    authentication_classes = [RecruiterCookieJWTAuthentication]
    permission_classes = [IsRecruiter]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recruiter"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def grant_or_404(self, drive_id):
        """Grant expiry/revocation is checked here on every request, in the permission path."""
        grant = services.valid_grant(self.request.user, drive_id)
        if grant is None:
            services.log_access(
                recruiter=self.request.user,
                grant=None,
                action=AccessAction.DENIED,
                request=self.request,
                drive_id=drive_id,
            )
            raise NotFound()
        return grant


class RecruiterMeView(RecruiterAPIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class MyDrivesView(RecruiterAPIView):
    @extend_schema(
        responses=inline_serializer(
            "RecruiterDrive",
            {
                "drive_id": serializers.IntegerField(),
                "company": serializers.CharField(),
                "role": serializers.CharField(),
                "drive_date": serializers.DateField(allow_null=True),
                "expires_at": serializers.DateTimeField(),
                "allowed_fields": serializers.ListField(),
                "candidate_scope": serializers.CharField(),
                "candidates": serializers.IntegerField(),
            },
            many=True,
        )
    )
    def get(self, request):
        rows = []
        for grant in services.valid_grants(request.user):
            rows.append(
                {
                    "drive_id": grant.drive_id,
                    "company": grant.drive.company.name,
                    "role": grant.drive.role_title,
                    "drive_date": grant.drive.drive_date,
                    "expires_at": grant.expires_at,
                    "allowed_fields": released_fields(grant),
                    "candidate_scope": grant.candidate_scope,
                    "candidates": services.scoped_candidates(grant).count(),
                }
            )
        return Response(rows)


class CandidatePagination(PageNumberPagination):
    page_size = 10
    max_page_size = 10  # No page_size override: browsing is deliberately incremental (no bulk export).


CANDIDATE_PARAMS = [
    OpenApiParameter("q", str, description="Skill to search for (taxonomy-expanded)"),
    OpenApiParameter("department", str, description="Department code (if department is released)"),
    OpenApiParameter("min_compatibility", float, description="If compatibility is released"),
    OpenApiParameter("page", int),
]


class CandidateListView(RecruiterAPIView):
    @extend_schema(
        parameters=CANDIDATE_PARAMS,
        responses=inline_serializer(
            "CandidatePage",
            {
                "count": serializers.IntegerField(),
                "next": serializers.CharField(allow_null=True),
                "previous": serializers.CharField(allow_null=True),
                "results": serializers.ListField(),
                "facets": serializers.DictField(),
                "fields": serializers.ListField(),
            },
        ),
    )
    def get(self, request, drive_id):
        grant = self.grant_or_404(drive_id)
        fields = set(released_fields(grant))
        qs = services.scoped_candidates(grant)  # Layer 1 first, before any filtering.
        query = {}

        q = request.query_params.get("q", "").strip()
        if q and "skills" in fields:
            matches = search_skills(grant.institution, q, limit=5)
            satisfying = SkillClosure.objects.filter(ancestor__in=matches).values("descendant_id")
            qs = qs.filter(pk__in=SkillClaim.objects.filter(skill_id__in=satisfying).values("student_id"))
            query["q"] = q
        department = request.query_params.get("department")
        if department and "department" in fields:
            qs = qs.filter(department__code__iexact=department)
            query["department"] = department
        min_compat = request.query_params.get("min_compatibility")
        if min_compat and "compatibility" in fields:
            try:
                threshold = float(min_compat)
            except ValueError:
                threshold = 0.0
            qs = qs.filter(
                pk__in=MatchResult.objects.filter(drive_id=grant.drive_id, compatibility__gte=threshold).values(
                    "student_id"
                )
            )
            query["min_compatibility"] = threshold

        students = list(qs.order_by("pk"))
        if "compatibility" in fields:
            scores = dict(
                MatchResult.objects.filter(drive_id=grant.drive_id, student__in=students).values_list(
                    "student_id", "compatibility"
                )
            )
            students.sort(key=lambda s: -(float(scores.get(s.pk) or 0)))

        facets = self._facets(grant, students, fields)
        paginator = CandidatePagination()
        page = paginator.paginate_queryset(students, request, view=self)
        ctx = load_context(grant, page, detail=False)
        results = [serialize_candidate(s, ctx) for s in page]
        services.log_access(
            recruiter=request.user,
            grant=grant,
            action=AccessAction.SEARCH if query else AccessAction.LIST,
            request=request,
            student_ids=[s.pk for s in page],
            fields=sorted(fields),
            drive_id=grant.drive_id,
            query=query,
        )
        response = paginator.get_paginated_response(results)
        response.data["facets"] = facets
        response.data["fields"] = sorted(fields)
        return response

    def _facets(self, grant, students, fields):
        """Counts computed from the scoped candidate set only, so they reveal nothing about
        students outside the drive."""
        ids = [s.pk for s in students]
        facets = {}
        if "department" in fields:
            facets["department"] = [
                {"value": code, "count": n} for code, n in Counter(s.department.code for s in students).most_common()
            ]
        if "skills" in fields:
            counts = Counter(
                SkillClaim.objects.filter(student_id__in=ids, skill__is_abstract=False).values_list(
                    "skill__name", flat=True
                )
            )
            facets["skills"] = [{"value": name, "count": n} for name, n in counts.most_common(12)]
        if "compatibility" in fields:
            scores = MatchResult.objects.filter(drive_id=grant.drive_id, student_id__in=ids).values_list(
                "compatibility", flat=True
            )
            bands = Counter(band_of(float(v)) for v in scores)
            facets["compatibility"] = [{"value": b, "count": n} for b, n in bands.items()]
        return facets


class CandidateDetailView(RecruiterAPIView):
    @extend_schema(
        operation_id="recruiter_candidate_detail",
        responses=inline_serializer("Candidate", {"id": serializers.IntegerField()}),
    )
    def get(self, request, drive_id, student_id):
        grant = self.grant_or_404(drive_id)
        student = services.scoped_candidates(grant).filter(pk=student_id).first()
        if student is None:
            services.log_access(
                recruiter=request.user,
                grant=grant,
                action=AccessAction.DENIED,
                request=request,
                student_ids=[int(student_id)],
                drive_id=grant.drive_id,
            )
            raise NotFound()
        ctx = load_context(grant, [student], detail=True)
        services.log_access(
            recruiter=request.user,
            grant=grant,
            action=AccessAction.DETAIL,
            request=request,
            student_ids=[student.pk],
            fields=sorted(ctx["fields"]),
            drive_id=grant.drive_id,
        )
        return Response(serialize_candidate(student, ctx), status=status.HTTP_200_OK)


class CandidateResumeView(RecruiterAPIView):
    """A short-lived link to a candidate's resume, only when the grant releases `resume`. Logged."""

    @extend_schema(
        operation_id="recruiter_candidate_resume",
        responses=inline_serializer(
            "CandidateResume", {"url": serializers.CharField(), "expires_in": serializers.IntegerField()}
        ),
    )
    def get(self, request, drive_id, student_id):
        from apps.students.resumes import signed_url
        from apps.students.services import current_resume

        grant = self.grant_or_404(drive_id)
        student = services.scoped_candidates(grant).filter(pk=student_id).first()
        resume = current_resume(student) if student is not None and "resume" in grant.allowed_fields else None
        if resume is None:
            services.log_access(
                recruiter=request.user,
                grant=grant,
                action=AccessAction.DENIED,
                request=request,
                student_ids=[int(student_id)],
                drive_id=grant.drive_id,
                query={"resume": True},
            )
            raise NotFound()
        services.log_access(
            recruiter=request.user,
            grant=grant,
            action=AccessAction.RESUME,
            request=request,
            student_ids=[student.pk],
            fields=["resume"],
            drive_id=grant.drive_id,
        )
        from django.conf import settings

        return Response({"url": signed_url(resume.file.name), "expires_in": settings.RESUME_URL_EXPIRY_SECONDS})
