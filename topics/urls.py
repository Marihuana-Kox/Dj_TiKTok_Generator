from django.urls import path
from . import views

app_name = 'topics'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('generate/', views.generate_idea_view, name='generate'),
    path('<int:pk>/edit/', views.project_edit, name='project_edit'),
]
