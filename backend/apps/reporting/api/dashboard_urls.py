from django.urls import path

from . import views

urlpatterns = [
    path("student/", views.StudentDashboardView.as_view(), name="dashboard-student"),
    path("faculty/", views.FacultyDashboardView.as_view(), name="dashboard-faculty"),
]
