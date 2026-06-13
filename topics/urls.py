from django.urls import path
from . import views

app_name = "topics"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("generate/", views.generate_idea_view, name="generate"),
    path("research/", views.generate_research_view, name="research"),
    path("dashboard-research/", views.dashboard_research, name="dashboard_research"),
    path("<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("edit-research/<int:pk>/", views.research_edit, name="research_edit"),
    path("api/generate-stream/", views.generate_stream, name="generate_stream"),
]
