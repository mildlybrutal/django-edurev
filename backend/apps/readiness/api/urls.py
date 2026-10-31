from django.urls import path

from . import views

urlpatterns = [
    path("config/", views.ScoringConfigView.as_view(), name="readiness-config"),
    path("evidence-rules/", views.EvidenceRuleListView.as_view(), name="evidence-rule-list"),
    path("evidence-rules/<int:rule_id>/", views.EvidenceRuleDetailView.as_view(), name="evidence-rule-detail"),
]
