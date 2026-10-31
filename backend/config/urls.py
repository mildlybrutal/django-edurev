from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.core import views as core_views

api_v1 = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("auth/", include("apps.accounts.api.urls")),
    path("skills/", include("apps.taxonomy.api.urls")),
    path("students/", include("apps.students.api.urls")),
    path("evidence/", include("apps.evidence.api.urls")),
    path("verification/", include("apps.verification.api.urls")),
    path("assessments/", include("apps.assessments.api.urls")),
    path("readiness/", include("apps.readiness.api.urls")),
    path("drives/", include("apps.drives.api.urls")),
    path("preparation-plans/", include("apps.planning.api.urls")),
    path("reports/", include("apps.reporting.api.urls")),
    path("dashboard/", include("apps.reporting.api.dashboard_urls")),
    path("notifications/", include("apps.notifications.api.urls")),
    path("recruiter/", include("apps.recruiter.api.urls")),
    path("recruiter-admin/", include("apps.recruiter.api.admin_urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", core_views.health, name="health"),
    path("ready", core_views.ready, name="ready"),
    path("api/v1/", include(api_v1)),
]
