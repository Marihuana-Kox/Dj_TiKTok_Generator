from django.urls import path
from . import views

app_name = 'generator'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('project/<int:pk>/', views.project_detail, name='project_detail'),
    path('project/<int:pk>/generate/', views.generate_config,
         name='generate_config'),  # Новый путь
]
