from django.urls import path

from . import views

urlpatterns = [
    path("queue/", views.QueueView.as_view(), name="verification-queue"),
    path("<int:evidence_id>/decide/", views.DecideView.as_view(), name="verification-decide"),
]
