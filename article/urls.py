from django.urls import path
from . import views

app_name = 'article'

urlpatterns = [
    # Страница редактора: /article/1/edit/
    path('', views.article_dashboard, name='dashboard'),
    path('generate-modal/', views.generation_modal, name='gen_modal'),
    path('generate-start/', views.start_generation, name='gen_start'),
    path('generate-stream/', views.generation_stream, name='gen_stream'),
    path('<int:pk>/edit/', views.article_editor, name='article_editor'),
]
