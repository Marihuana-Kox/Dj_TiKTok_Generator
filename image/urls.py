from django.urls import path
from . import views

app_name = 'image'

urlpatterns = [
    # Главная страница приложения (список проектов)
    path('', views.image_dashboard, name='dashboard'),
    path('create/', views.project_create, name='project_create'),
    path('<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('api/generation-progress/<str:task_id>/',
         views.generation_progress, name='generation_progress'),
    path('api/generation-stream/', views.generation_stream,
         name='generation_stream'),
]
