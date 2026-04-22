from django.urls import path
from . import views

app_name = 'image'

urlpatterns = [
    path('<int:pk>/prompts/', views.image_prompt_editor,
         name='image_prompt_editor'),
]
