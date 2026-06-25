from django.urls import path
from . import views

app_name = "article"

urlpatterns = [
    # Страница редактора: /article/1/edit/
    path("", views.article_dashboard, name="dashboard"),
    path("create/", views.article_create, name="article_create"),
    path("generate/", views.article_generate_page, name="generate_page"),
    path("scripts-dashboard/", views.script_dashboard, name="script_dashboard"),
    path("scripts-generate/", views.script_generate, name="script_generate"),
    path("scripts_detail/<int:pk>", views.script_detail, name="script_detail"),
    path("api/start-generation/", views.start_generation_api, name="start_generation_api"),
    path("api/generation-stream/", views.generation_stream, name="generation_stream"),
    path("editor/<int:cluster_id>/ai-translate/", views.ai_translate, name="ai_translate"),
    path("<int:pk>/edit/", views.article_editor, name="article_editor"),
]
