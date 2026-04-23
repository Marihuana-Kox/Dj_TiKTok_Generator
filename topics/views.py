import sys
import traceback
import time
import threading
from .forms import GenerateIdeasForm
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import VideoProject
# Нам понадобится форма (см. ниже)
from .forms import GenerateIdeasForm, VideoProjectEditForm
from .services import generate_unique_ideas
from django.http import StreamingHttpResponse
import json

# Глобальное хранилище прогресса (в памяти)
# Ключ: session_key пользователя, Значение: dict с данными прогресса
GENERATION_PROGRESS = {}


def generate_idea_view(request):
    if request.method == 'POST':
        form = GenerateIdeasForm(request.POST)
        if form.is_valid():
            # Подготовка данных
            provider_name = form.cleaned_data['ai_provider']
            count = form.cleaned_data['count']
            # Получаем выбранный стиль (может быть 'random' или конкретный код)
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

            # Инициализируем прогресс для этой сессии
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            GENERATION_PROGRESS[session_key] = {
                'current': 0,
                'total': count,
                'message': 'Инициализация...',
                'percent': 0,
                'status': 'starting'
            }

            # Запускаем генерацию в отдельном потоке, чтобы не блокировать SSE
            def run_generation():
                try:
                    # Callback функция, которая будет обновлять прогресс
                    def callback(current, total, step, message, idea_id):
                        percent = int((current / total) * 100)
                        GENERATION_PROGRESS[session_key] = {
                            'current': current,
                            'total': total,
                            'message': message,
                            'percent': percent,
                            'step': step,
                            'idea_id': idea_id,
                            'status': 'running'
                        }

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

                    # Финал
                    GENERATION_PROGRESS[session_key]['status'] = 'done'
                    GENERATION_PROGRESS[session_key]['percent'] = 100
                    GENERATION_PROGRESS[session_key]['message'] = 'Готово! Перенаправление...'

                    messages.success(
                        request, f"✅ Успешно сгенерировано {count} идей!")

                except Exception as e:
                    GENERATION_PROGRESS[session_key]['status'] = 'error'
                    GENERATION_PROGRESS[session_key]['message'] = f"Ошибка: {str(e)}"
                    messages.error(request, f"❌ Ошибка генерации: {str(e)}")

            # Запуск потока
            thread = threading.Thread(target=run_generation)
            thread.start()

            # Возвращаем страницу с формой (прогресс-бар появится сам через JS)
            return render(request, 'topics/generate.html', {'form': form})
        else:
            messages.error(request, "Ошибка в форме. Проверьте данные.")
    else:
        form = GenerateIdeasForm()

    return render(request, 'topics/generate.html', {'form': form})


def generate_stream(request):
    """SSE Endpoint"""
    session_key = request.session.session_key
    if not session_key:
        # Если сессии нет, возвращаем пустой поток, а не None
        def empty_stream():
            yield ""
        response = StreamingHttpResponse(
            empty_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        return response

    def event_stream():
        last_percent = -1

        # Ждем, пока появится запись в прогрессе (на случай гонки потоков)
        import time
        time.sleep(0.5)

        while True:
            data = GENERATION_PROGRESS.get(session_key)

            if data:
                # Отправляем данные если процент изменился или статус финальный
                if data['percent'] != last_percent or data.get('status') in ['done', 'error']:
                    yield f"data: {json.dumps(data)}\n\n"
                    last_percent = data['percent']

                if data.get('status') in ['done', 'error']:
                    # Даем время клиенту получить последнее сообщение
                    time.sleep(1)
                    break
            else:
                # Если данных еще нет, ждем
                yield f"data: {{'status': 'waiting', 'message': 'Initializing...'}}\n\n"

            time.sleep(0.5)

        # Очистка
        if session_key in GENERATION_PROGRESS:
            del GENERATION_PROGRESS[session_key]

    response = StreamingHttpResponse(
        event_stream(), content_type='text/event-stream')
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


def generate_idea_view(request):
    if request.method == 'POST':
        form = GenerateIdeasForm(request.POST)
        if form.is_valid():
            topic = form.cleaned_data['topic']
            count = form.cleaned_data['count']

            try:
                created_count = generate_unique_ideas(count=count, topic=topic)
                messages.success(
                    request, f"✅ Успешно сгенерировано {created_count} новых идей!")
                return redirect('topics:dashboard')
            except Exception as e:
                messages.error(request, f"❌ Ошибка: {str(e)}")
    else:
        form = GenerateIdeasForm()

    return render(request, 'topics/generate.html', {'form': form})


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


def generate_idea_view(request):
    if request.method == 'POST':
        form = GenerateIdeasForm(request.POST)
        if form.is_valid():
            provider_name = form.cleaned_data['ai_provider']
            count = form.cleaned_data['count']
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

            print(
                f"\n🚀 START GENERATION: Provider={provider_name}, Count={count}")

            try:
                # Вызов сервиса
                created_count = generate_unique_ideas(
                    provider_name=provider_name,
                    count=count,
                    topic=main_topic,
                    focus_topics=focus_topics,
                    refresh_old=refresh_old,
                    refresh_days=refresh_period,
                    allow_duplicates=allow_duplicates,
                    no_duplicate_days=duplicate_period
                )

                print(f"✅ SUCCESS: Created {created_count} ideas.")
                messages.success(
                    request, f"✅ {provider_name.upper()} сгенерировал {created_count} идей!")
                return redirect('topics:dashboard')

            except Exception as e:
                # ЛОВИМ ОШИБКУ И ВЫВОДИМ ПОДРОБНОСТИ
                error_msg = str(e)
                full_traceback = traceback.format_exc()

                print(f"\n❌ CRITICAL ERROR DURING GENERATION:")
                print(f"Error Message: {error_msg}")
                print(f"Traceback:\n{full_traceback}")
                print("-" * 50)

                # Показываем ошибку пользователю в интерфейсе
                messages.error(
                    request, f"❌ Ошибка генерации ({provider_name}): {error_msg}")
                # Возвращаем пользователя обратно на форму, чтобы он не потерял введенные данные
                return render(request, 'topics/generate.html', {'form': form})
        else:
            print("⚠️ Form is invalid:", form.errors)
            messages.error(request, "Проверьте правильность заполнения формы.")
    else:
        form = GenerateIdeasForm()

    return render(request, 'topics/generate.html', {'form': form})


def generate_stream(request):
    def event_stream():
        # Запускаем генерацию с callback-ом, который шлет данные в поток
        def progress_callback(current, total, msg, idea_id):
            percent = int((current / total) * 100)
            data = {
                'current': current,
                'total': total,
                'percent': percent,
                'message': msg,
                'idea_id': idea_id,
                'status': 'done' if current == total else 'working'
            }
            yield f"data: {json.dumps(data)}\n\n"

        # Запуск тяжелой функции (в будущем лучше вынести в Celery, но для старта пойдет так)
        # Нужно будет адаптировать вызов, чтобы он работал внутри генератора
        pass

    response = StreamingHttpResponse(
        event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response
