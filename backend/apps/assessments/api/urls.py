from django.urls import path

from . import views

urlpatterns = [
    path("", views.AssessmentListView.as_view(), name="assessment-list"),
    path("rubrics/", views.RubricListView.as_view(), name="rubric-list"),
    path("mock-interviews/", views.MockInterviewListView.as_view(), name="mock-interview-list"),
]
