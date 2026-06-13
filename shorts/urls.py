from django.urls import path

from . import views

app_name = "shorts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("generate_stream/", views.generate_stream, name="generate_stream"),
    path("generate/", views.generate, name="generate"),
    path("<int:pk>/", views.detail, name="detail"),
]
