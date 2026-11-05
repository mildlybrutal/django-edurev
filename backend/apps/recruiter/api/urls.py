from django.urls import path

from . import views

# Recruiter portal: its own namespace, authentication class, cookies and throttle scope (P06 §7, §16).
# Candidate data is read-only by design: there is no export endpoint. The only write is a
# broadcast to the drive's own scoped candidates.
urlpatterns = [
    path("auth/login/", views.RecruiterLoginView.as_view(), name="recruiter-login"),
    path("auth/mfa/verify/", views.RecruiterMFAVerifyView.as_view(), name="recruiter-mfa-verify"),
    path("auth/refresh/", views.RecruiterRefreshView.as_view(), name="recruiter-refresh"),
    path("auth/logout/", views.RecruiterLogoutView.as_view(), name="recruiter-logout"),
    path("me/", views.RecruiterMeView.as_view(), name="recruiter-me"),
    path("drives/", views.MyDrivesView.as_view(), name="recruiter-drives"),
    path("drives/<int:drive_id>/candidates/", views.CandidateListView.as_view(), name="recruiter-candidates"),
    path("drives/<int:drive_id>/broadcasts/", views.BroadcastView.as_view(), name="recruiter-broadcasts"),
    path(
        "drives/<int:drive_id>/candidates/<int:student_id>/resume/",
        views.CandidateResumeView.as_view(),
        name="recruiter-candidate-resume",
    ),
    path(
        "drives/<int:drive_id>/candidates/<int:student_id>/",
        views.CandidateDetailView.as_view(),
        name="recruiter-candidate",
    ),
]
