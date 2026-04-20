from django.urls import path
from . import views

app_name = 'config'  # <-- ЭТО КРИТИЧЕСКИ ВАЖНО! Это регистрирует namespace

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
