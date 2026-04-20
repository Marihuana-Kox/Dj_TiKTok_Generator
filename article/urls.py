from django.urls import path
from . import views

app_name = 'article'

urlpatterns = [
    # Страница редактора: /article/1/edit/
    path('<int:pk>/edit/', views.article_editor, name='article_editor'),
]
