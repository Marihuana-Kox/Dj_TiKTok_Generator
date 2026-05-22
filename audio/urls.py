from django.urls import path
from . import views

app_name = "audio"

urlpatterns = [
    path("", views.audio_dashboard, name="dashboard"),
    path("create/", views.audio_create, name="audio_create"),
    path("<int:pk>/edit/", views.audio_edit, name="audio_edit"),
    path(
        "api/generation-progress/",
        views.generation_progress,
        name="generation_progress_query",
    ),
    path(
        "api/generation-progress/<str:task_id>/",
        views.generation_progress,
        name="generation_progress",
    ),
    path("api/generation-stream/", views.generation_stream, name="generation_stream"),
    path(
        "track/<int:track_id>/synthesize/",
        views.synthesize_single_track,
        name="synthesize_single_track",
    ),
    # Для массовой кнопки (не передает ID в URL, так как мы шлем массив в теле POST-запроса)
    path(
        "track/synthesize/",
        views.synthesize_single_track,
        name="synthesize_mass_tracks",
    ),
    # path(
    #     "track/<int:track_id>/synthesize/",
    #     views.synthesize_single_track,
    #     name="synthesize_track",
    # ),
    # ⚡ НОВЫЙ РОУТ ДЛЯ ПРОСТОГО СОХРАНЕНИЯ ТЕКСТА
    path(
        "track/<int:track_id>/save-text/",
        views.save_track_text_ajax,
        name="save_track_text_ajax",
    ),
]
