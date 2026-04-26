import json
from django.core.cache import cache
import time
import threading
import uuid
from django.contrib import messages
from django.http import StreamingHttpResponse

from topics.models import VideoProject
from .forms import GenerateIdeasForm, VideoProjectEditForm
from django.shortcuts import render, redirect, get_object_or_404
from .services import generate_unique_ideas

# Время жизни записи в кэше (секунды).
# Прогресс будет храниться 1 час, даже если что-то пойдет не так.
CACHE_TIMEOUT = 3600


def generate_idea_view(request):
    if request.method == 'POST':
        form = GenerateIdeasForm(request.POST)
        if form.is_valid():
            # 1. Генерируем уникальный ID для этой конкретной задачи
            task_id = str(uuid.uuid4())

            # Подготовка данных из формы
            provider_name = form.cleaned_data['ai_provider']
            count = form.cleaned_data['count']
            idea_style = form.cleaned_data.get('idea_style', 'random')
            topics_raw = form.cleaned_data.get('topics_input', '')
            focus_topics = [t.strip()
                            for t in topics_raw.split('\n') if t.strip()]
            main_topic = ", ".join(focus_topics) if focus_topics else "История"

            refresh_old = form.cleaned_data.get('refresh_old', False)
            refresh_period = int(form.cleaned_data.get(
                'refresh_period', 30)) if refresh_old else None
            allow_duplicates = form.cleaned_data.get('allow_duplicates', False)
            duplicate_period = int(form.cleaned_data.get(
                'duplicate_period', 30)) if not allow_duplicates else None

            # Генерируем уникальный ID задачи
            task_id = str(uuid.uuid4())

            # Сохраняем task_id в сессии для текущего пользователя
            request.session['current_task_id'] = task_id
            # 2. Инициализируем прогресс в КЭШЕ вместо глобальной переменной
            initial_data = {
                'current': 0,
                'total': count,
                'message': 'Инициализация...',
                'percent': 0,
                'status': 'starting',
                'task_id': task_id
            }
            # Сохраняем в кэш под ключом, включающим task_id
            cache.set(f"progress_{task_id}", initial_data, timeout=300)

            # Функция запуска в фоне
            def run_generation():
                try:
                    # Callback функция для обновления прогресса
                    def callback(current, total, step, message, idea_id):
                        percent = int((current / total) *
                                      100) if total > 0 else 0

                        progress_data = {
                            'current': current,
                            'total': total,
                            'message': message,
                            'percent': percent,
                            'step': step,
                            'idea_id': idea_id,
                            'status': 'running',
                            'task_id': task_id
                        }
                        # Обновляем данные в кэше
                        cache.set(f"progress_{task_id}",
                                  progress_data, timeout=300)

                    # Запуск основной функции генерации
                    generate_unique_ideas(
                        provider_name=provider_name,
                        count=count,
                        topic=main_topic,
                        focus_topics=focus_topics,
                        idea_style=idea_style,
                        refresh_old=refresh_old,
                        refresh_days=refresh_period,
                        allow_duplicates=allow_duplicates,
                        no_duplicate_days=duplicate_period,
                        callback=callback
                    )

                    final_data = {
                        'current': count,
                        'total': count,
                        'message': 'Готово! Перенаправление...',
                        'percent': 100,
                        'status': 'done',
                        'task_id': task_id
                    }
                    cache.set(f"progress_{task_id}", final_data, timeout=60)

                    messages.success(
                        request, f"✅ Успешно сгенерировано {count} идей!")

                except Exception as e:
                    error_data = {
                        'current': 0,
                        'total': count,
                        'message': f"Ошибка: {str(e)}",
                        'percent': 0,
                        'status': 'error',
                        'task_id': task_id
                    }
                    cache.set(f"progress_{task_id}", error_data, timeout=60)
                    messages.error(request, f"❌ Ошибка генерации: {str(e)}")

            # Запуск потока
            thread = threading.Thread(target=run_generation)
            thread.daemon = True  # Поток умрет вместе с основным процессом при перезагрузке
            thread.start()

            # Возвращаем страницу с формой и task_id
            return render(request, 'topics/generate.html', {'form': form, 'task_id': task_id})
        else:
            messages.error(request, "Ошибка в форме. Проверьте данные.")
    else:
        form = GenerateIdeasForm()
        # При обычном заходе страницы task_id нет
        return render(request, 'topics/generate.html', {'form': form})


def generate_stream(request):
    """SSE Endpoint для генерации идей"""
    # Получаем task_id из GET параметров (?task_id=...)
    task_id = request.GET.get('task_id')

    if not task_id:
        # Если ID нет, возвращаем пустой поток, чтобы не ломать соединение
        def empty_stream():
            yield ""
        response = StreamingHttpResponse(
            empty_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        return response

    def event_stream():
        last_percent = -1
        last_message = ""
        start_time = time.time()
        timeout = 120  # Максимальное время ожидания (2 минуты)

        # Ждем немного, чтобы фоновый процесс успел создать запись в кэше
        time.sleep(0.5)

        while True:
            # Читаем данные из КЭША
            # Проверяем таймаут
            if time.time() - start_time > timeout:
                break

            data = cache.get(f"progress_{task_id}")

            # Отправляем данные если процент или сообщение изменились
            if (data.get('percent', 0) != last_percent or
                data.get('message', '') != last_message or
                    data.get('status') in ['done', 'error']):

                payload = json.dumps(data)
                yield f"data: {payload}\n\n"

                last_percent = data.get('percent', 0)
                last_message = data.get('message', '')

                # Если процесс завершен - выходим
                if data.get('status') in ['done', 'error']:
                    # Даем время браузеру получить последний пакет
                    time.sleep(0.5)
                    cache.delete(f"progress_{task_id}")
                    break
            else:
                pass

            time.sleep(0.5)

    response = StreamingHttpResponse(
        event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Connection'] = 'keep-alive'
    return response


def dashboard(request):
    # --- ОБРАБОТКА УДАЛЕНИЯ ---
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_selected':
            selected_ids = request.POST.getlist('selected_ideas')
            if selected_ids:
                count, _ = VideoProject.objects.filter(
                    id__in=selected_ids).delete()
                messages.success(request, f"✅ Удалено {count} идей.")
            else:
                messages.warning(request, "⚠️ Вы не выбрали ни одной идеи.")
            return redirect('topics:dashboard')
    # Статистика
    stats = {
        'total': VideoProject.objects.count(),
        'new': VideoProject.objects.filter(status='pending').count(),
        'done': VideoProject.objects.filter(status='completed').count(),
    }
    # Список последних идей
    ideas = VideoProject.objects.all().order_by('-created_at')[:50]

    context = {
        'stats': stats,
        'ideas': ideas,
    }
    return render(request, 'topics/dashboard.html', context)


def project_edit(request, pk):
    # Получаем проект или 404
    project = get_object_or_404(VideoProject, pk=pk)

    if request.method == 'POST':
        form = VideoProjectEditForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Идеи успешно сохранены!")
            # Перезагружаем страницу, чтобы увидеть изменения
            return redirect('topics:project_edit', pk=pk)
        else:
            messages.error(request, "❌ Ошибка при сохранении. Проверьте поля.")
    else:
        # Если GET запрос, просто создаем форму с текущими данными
        form = VideoProjectEditForm(instance=project)

    context = {
        'form': form,
        'project': project
    }
    return render(request, 'topics/project_edit.html', context)
