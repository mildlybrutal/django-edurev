from django.urls import path

from . import admin_views as views

urlpatterns = [
    path("fields/", views.ReleasableFieldsView.as_view(), name="recruiter-admin-fields"),
    path("recruiters/", views.RecruiterListView.as_view(), name="recruiter-admin-recruiters"),
    path("grants/", views.GrantListView.as_view(), name="recruiter-admin-grants"),
    path("grants/<int:grant_id>/", views.GrantDetailView.as_view(), name="recruiter-admin-grant"),
    path("access-logs/", views.AccessLogListView.as_view(), name="recruiter-admin-logs"),
]
