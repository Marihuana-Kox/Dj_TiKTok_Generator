from django.urls import path

from . import views

app_name = "shorts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("generate/", views.generate, name="generate"),
    path("generate_stream/", views.generate_stream, name="generate_stream"),
    path("detail/<int:pk>/", views.detail, name="detail"),
]
