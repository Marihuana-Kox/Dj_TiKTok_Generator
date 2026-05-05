from django.shortcuts import render


def home_page(request):
    """Главная страница сервиса"""
    return render(request, 'main/index.html')
