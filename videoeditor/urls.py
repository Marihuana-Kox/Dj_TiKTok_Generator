from django.urls import path
from . import views

app_name = "videoeditor"

urlpatterns = [
    # Роут будет принимать ID проекта аудио (или общий ID проекта)
    path("project/<int:project_id>/edit/", views.video_editor_view, name="editor"),
]
