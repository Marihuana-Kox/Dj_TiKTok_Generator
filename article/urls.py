from django.urls import path
from . import views

app_name = 'article'

urlpatterns = [
    # Страница редактора: /article/1/edit/
    path('', views.article_dashboard, name='dashboard'),
    path('generate/', views.article_generate_page, name='generate_page'),
    path('api/start-generation/', views.start_generation_api,
         name='start_generation_api'),
    path('api/generation-stream/', views.generation_stream,
         name='generation_stream'),
    path('<int:pk>/edit/', views.article_editor, name='article_editor'),
]
