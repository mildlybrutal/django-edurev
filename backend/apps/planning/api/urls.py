from django.urls import path

from . import views

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("resources/", views.ResourceListView.as_view(), name="resource-list"),
    path("items/<int:item_id>/", views.PlanItemView.as_view(), name="plan-item"),
    path("<int:plan_id>/", views.PlanDetailView.as_view(), name="plan-detail"),
]
