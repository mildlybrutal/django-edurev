from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view(), name="report-overview"),
    path("demand/", views.DemandAcrossDrivesView.as_view(), name="report-demand"),
    path("gaps/", views.GapFrequencyView.as_view(), name="report-gaps"),
    path("verification-coverage/", views.VerificationCoverageView.as_view(), name="report-verification"),
    path("departments/", views.DepartmentComparisonView.as_view(), name="report-departments"),
    path("training-effectiveness/", views.TrainingEffectivenessView.as_view(), name="report-training"),
    path("drives/<int:drive_id>/supply-demand/", views.SupplyDemandView.as_view(), name="report-supply-demand"),
    path("drives/<int:drive_id>/funnel/", views.FunnelView.as_view(), name="report-funnel"),
    path("batch-readiness/", views.BatchReadinessView.as_view(), name="report-batch-readiness"),
    path("jobs/<int:job_id>/", views.JobView.as_view(), name="report-job"),
]
