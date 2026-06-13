from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("generate/", views.generate, name="generate"),
    path("detail/<int:pk>/", views.detail, name="detail"),
    path("generate_stream/<str:task_id>/", views.generate_stream, name="generate_stream"),
]
