from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse


def home_page(request):
    """Главная страница сервиса"""
    return render(request, 'main/index.html')

# views.py (в общем модуле или прямо в текущем)


@login_required
def global_cancel_task(request, task_id):
    if request.method == 'POST':
        # Просто находим задачу в кэше по ID и ставим статус cancelled
        # Кэш один на весь проект, поэтому это сработает везде
        cache_key = f"progress_{task_id}"
        data = cache.get(cache_key)
        if data:
            data['status'] = 'cancelled'
            data['message'] = '⛔ Прервано пользователем'
            cache.set(cache_key, data, timeout=60)
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
