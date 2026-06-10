from django.urls import path
from . import views

app_name = "videoeditor"

urlpatterns = [
    path("projects/", views.projects_list, name="list"),
    path("project/<int:project_id>/", views.video_editor_view, name="video_editor"),
    path("project/<int:project_id>/save-draft/", views.save_live_draft, name="save_live_draft"),
    path("project/<int:project_id>/download/", views.download_video_file, name="download_video"),
    path(
        "project/<int:project_id>/start-render/",
        views.start_video_render,
        name="start_video_render",
    ),
    path(
        "project/<int:project_id>/restore-config/<str:config_id>/",
        views.restore_config_view,
        name="restore_config",
    ),
]
