from django.urls import path

from apps.coding.api import views as coding_views

from . import views

urlpatterns = [
    path("", views.StudentListView.as_view(), name="student-list"),
    path("departments/", views.DepartmentListView.as_view(), name="department-list"),
    path("faculty/", views.FacultyListView.as_view(), name="faculty-list"),
    path("me/onboarding/", views.OnboardingView.as_view(), name="student-onboarding"),
    path("me/coding/refresh/", coding_views.CodingRefreshView.as_view(), name="student-coding-refresh"),
    path("<str:student_id>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("<str:student_id>/profile/", views.SkillProfileView.as_view(), name="student-profile"),
    path("<str:student_id>/readiness/", views.ReadinessView.as_view(), name="student-readiness"),
    path("<str:student_id>/coding/", coding_views.CodingView.as_view(), name="student-coding"),
    path("<str:student_id>/resume/", views.ResumeView.as_view(), name="student-resume"),
]
