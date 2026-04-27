import json
from django.core.cache import cache
import time
import threading
import uuid
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from topics.models import VideoProject
from .forms import GenerateIdeasForm, VideoProjectEditForm
from django.shortcuts import render, redirect, get_object_or_404
from .services import generate_unique_ideas

# Время жизни записи в кэше (секунды).
# Прогресс будет храниться 1 час, даже если что-то пойдет не так.
CACHE_TIMEOUT = 3600


def generate_idea_view(request):
    """Основное view для генерации идей с прогресс-баром"""
    task_id = None

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
                    # 🚀 1. Мгновенный старт (чтобы не было 0%)
                    cache.set(f"progress_{task_id}", {
                        'current': 0,
                        'total': count,
                        'message': 'Запуск генерации...',
                        'percent': 1,
                        'status': 'running',
                        'task_id': task_id
                    }, timeout=300)
                    # 🔁 Callback

                    def callback(current, total, step, message, idea_id):
                        print("CALLBACK:", current, total)

                        percent = int((current / total) *
                                      100) if total > 0 else 0

                        # ⚠️ ограничим до 95%, чтобы финал был плавный
                        percent = min(percent, 95)

                        progress_data = {
                            'current': current,
                            'total': total,
                            'message': message or f"Обработка {current}/{total}",
                            'percent': percent,
                            'step': step,
                            'idea_id': idea_id,
                            'status': 'running',
                            'task_id': task_id
                        }

                        cache.set(f"progress_{task_id}",
                                  progress_data, timeout=300)
                        # 🧠 2. Псевдо-прогресс (если AI тупит)

                    def fake_progress():
                        percent = 1
                        while True:
                            data = cache.get(f"progress_{task_id}")
                            if not data or data.get('status') != 'running':
                                break

                            current_percent = data.get('percent', 1)

                            # если реальный прогресс стоит — двигаем медленно
                            if current_percent < percent + 5:
                                percent = min(percent + 1, 90)

                                data['percent'] = percent
                                data['message'] = data.get(
                                    'message') or "Генерация..."
                                cache.set(
                                    f"progress_{task_id}", data, timeout=300)

                            time.sleep(0.5)

                    # запускаем фейковый прогресс в фоне
                    threading.Thread(target=fake_progress, daemon=True).start()
                    # Запуск основной функции генерации
                    # ⚙️ 3. Основная генерация
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
                        'message': 'Готово! Запись в базу данных...',
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
            # Небольшая задержка чтобы поток успел создать запись в кэше
            time.sleep(0.2)

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
    task_id = request.GET.get('task_id')

    if not task_id:
        def empty(
        ): yield "data: {\"status\": \"error\", \"message\": \"No Task ID\"}\n\n"
        return StreamingHttpResponse(empty(), content_type='text/event-stream')


def generate_stream(request):
    """SSE Endpoint для генерации идей"""
    task_id = request.GET.get('task_id')

    # Вложенная функция-генератор
    def event_stream(t_id):
        last_percent = -1
        last_message = ""
        start_time = time.time()
        timeout = 600  # 10 минут

        while True:
            # 1. Проверка таймаута
            if time.time() - start_time > timeout:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Timeout'})}\n\n"
                break

            # 2. Получаем данные из кэша
            data = cache.get(f"progress_{t_id}")

            if not data:
                # Если данных нет, просто ждем. Не возвращаем None!
                yield f"data: {json.dumps({'status': 'waiting', 'message': 'Подключение к задаче...'})}\n\n"
                time.sleep(2)
                continue

            current_status = data.get('status')
            current_percent = data.get('percent', 0)
            current_message = data.get('message', '')

            # 3. Отправляем данные при изменениях
            if current_percent != last_percent or current_message != last_message or current_status in ['done', 'error']:
                yield f"data: {json.dumps(data)}\n\n"
                last_percent = current_percent
                last_message = current_message

                if current_status in ['done', 'error']:
                    time.sleep(1)
                    break

            time.sleep(1)

    # ГАРАНТИРОВАННЫЙ ВОЗВРАТ ОБЪЕКТА
    if not task_id:
        # Если task_id нет, возвращаем поток с ошибкой сразу
        def error_gen():
            yield f"data: {json.dumps({'status': 'error', 'message': 'No task_id provided'})}\n\n"
        return StreamingHttpResponse(error_gen(), content_type='text/event-stream')

    # Основной рабочий поток
    response = StreamingHttpResponse(event_stream(
        task_id), content_type='text/event-stream')
    response['Content-Type'] = 'text/event-stream'
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
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
        'new': VideoProject.objects.filter(status='new').count(),
        'pending': VideoProject.objects.filter(status='pending').count(),
        'done': VideoProject.objects.filter(status='completed').count(),
    }
    # Список последних идей
    ideas = VideoProject.objects.all().order_by('-created_at')[:50]
    # --- НАСТРОЙКА ПАГИНАЦИИ ---
    page_number = request.GET.get('page', 1)  # Номер страницы из URL (?page=2)
    paginator = Paginator(ideas, 20)  # Показывать по 10 идей на странице

    try:
        ideas_page = paginator.page(page_number)
    except PageNotAnInteger:
        ideas_page = paginator.page(1)
    except EmptyPage:
        ideas_page = paginator.page(paginator.num_pages)

    context = {
        'stats': stats,
        'ideas': ideas_page,
        'page_obj': ideas_page
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
