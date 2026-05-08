from django.urls import path
from . import views

app_name = 'audio'

urlpatterns = [
    path('', views.audio_dashboard, name='dashboard'),
    path('create/', views.audio_create, name='audio_create'),
    path('<int:pk>/edit/', views.audio_edit, name='audio_edit'),
]
