import uuid
import threading
import time
import json
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404

from topics.models import VideoProject
from .forms import GenerateIdeasForm, VideoProjectEditForm
from .services import generate_unique_ideas

# Время жизни записи в кэше (секунды).
# Прогресс будет храниться 1 час, даже если что-то пойдет не так.
CACHE_TIMEOUT = 3600


def generate_idea_view(request):
    """Основное view для генерации идей с прогресс-баром"""
    if request.method == "POST":
        # 1. Сбор данных (JSON или POST)
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body)
                form = GenerateIdeasForm(data)
            except json.JSONDecodeError:
                return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
        else:
            form = GenerateIdeasForm(request.POST)

        if form.is_valid():
            task_id = str(uuid.uuid4())

            # Извлекаем данные формы
            cd = form.cleaned_data
            provider_name = cd["ai_provider"]
            count = cd["count"]
            idea_style = cd.get("idea_style", "random")
            topics_raw = cd.get("topics_input", "")

            # Обработка тем
            focus_topics = [
                t.strip() for t in topics_raw.replace("\n", ",").split(",") if t.strip()
            ]
            main_topic = ", ".join(focus_topics) if focus_topics else "Общие темы"

            # Настройки БД
            refresh_old = cd.get("refresh_old", False)
            refresh_period = int(cd.get("refresh_period", 30)) if refresh_old else None
            allow_duplicates = cd.get("allow_duplicates", False)
            duplicate_period = int(cd.get("duplicate_period", 30)) if not allow_duplicates else None

            # Инициализация кэша
            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 1,
                    "message": "Инициализация...",
                    "status": "running",
                    "logs": ["🚀 Запуск генерации..."],
                },
                timeout=600,
            )

            def run_generation():
                try:
                    # Функция-помощник для обновления кэша без потери логов
                    def update_cache(percent, message, status="running", final=False):
                        current_data = cache.get(f"progress_{task_id}", {})
                        logs = current_data.get("logs", [])
                        if message and (not logs or logs[-1] != message):
                            logs.append(message)

                        new_data = {
                            "percent": percent,
                            "message": message,
                            "status": status,
                            "logs": logs[-15:],  # Храним последние 15 записей
                            "task_id": task_id,
                        }
                        if final:
                            new_data["redirect_url"] = "/topics/"
                        cache.set(f"progress_{task_id}", new_data, timeout=600)

                    # Вложенный callback для самой функции генерации
                    def callback(current, total, step, message, idea_id):
                        # Рассчитываем процент (макс 90% до финальной записи в БД)
                        if total > 0:
                            # Базовая часть: каждая идея дает вклад, но не до конца
                            # Например, если 1/10, то base = 8%
                            base_percent = int((current / total) * 85)

                            # Добавим "смещение" в зависимости от текущей идеи,
                            # чтобы бар не прыгал сразу на 20%, а рос внутри шага
                            percent = max(5, base_percent)
                        else:
                            percent = 5
                        update_cache(percent, message or f"Генерация идеи {current} из {total}...")

                    # --- ЗАПУСК ГЕНЕРАЦИИ ---
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
                        callback=callback,
                    )
                    final_steps = [
                        (92, "💾 Подготовка данных для сохранения..."),
                        (94, "🔍 Валидация структуры идей..."),
                        (97, "📝 Запись в базу данных..."),
                        (99, "⚙️ Финализация транзакций..."),
                    ]

                    for p, msg in final_steps:
                        update_cache(p, msg)
                        # Даем JS время "прокрутить" цифры до этих значений
                        time.sleep(1.2)

                    # 4. Полное завершение
                    update_cache(100, "✅ Все идеи успешно сохранены!", status="done", final=True)

                    print(f"🏁 Задача {task_id} завершена.")

                except Exception as e:
                    print(f"❌ Ошибка в потоке: {e}")
                    cache.set(
                        f"progress_{task_id}",
                        {"status": "error", "message": f"Ошибка: {str(e)}", "percent": 0},
                        timeout=60,
                    )
                finally:
                    from django.db import connection

                    connection.close()  # Важно для threading!

            # Запуск фонового процесса
            thread = threading.Thread(target=run_generation, daemon=True)
            thread.start()

            # Ответ для фронтенда
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.content_type == "application/json"
            ):
                return JsonResponse({"status": "ok", "task_id": task_id})

            return render(request, "topics/generate.html", {"form": form, "task_id": task_id})

        else:
            if request.content_type == "application/json":
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
            messages.error(request, "Ошибка в форме.")

    else:
        form = GenerateIdeasForm()

    return render(request, "topics/generate.html", {"form": form})


def generate_stream(request):
    """SSE поток, который РЕАЛЬНО читает прогресс из кэша"""
    task_id = request.GET.get("task_id")

    def event_stream(t_id):
        last_percent = -1

        while True:
            # Читаем то, что пишет функция run_generation
            data = cache.get(f"progress_{t_id}")

            if not data:
                # Если задача еще не успела создаться в кэше
                yield f"data: {json.dumps({'status': 'waiting', 'message': 'Подключение...'})}\n\n"
                time.sleep(1)
                continue

            current_status = data.get("status")
            current_percent = data.get("percent", 0)

            # Отправляем данные только если есть изменения
            if current_percent != last_percent or current_status in ["done", "error"]:
                yield f"data: {json.dumps(data)}\n\n"
                last_percent = current_percent

                # Если сервер проставил 'done', закрываем поток SSE
                if current_status in ["done", "error"]:
                    break

            time.sleep(1)  # Проверяем кэш раз в секунду

    if not task_id:
        return JsonResponse({"error": "No task_id"}, status=400)

    response = StreamingHttpResponse(event_stream(task_id), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def dashboard(request):
    # --- ОБРАБОТКА УДАЛЕНИЯ И СМЕНЫ СТАТУСА ---
    if request.method == "POST":
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_ideas")

        if selected_ids:
            ideas = VideoProject.objects.filter(id__in=selected_ids)

            if action == "delete_selected":
                count, _ = ideas.delete()
                messages.success(request, f"✅ Удалено {count} идей.")

            elif action == "change_status":
                new_status = request.POST.get("new_status")
                if new_status:
                    # Обновляем статус у всех выбранных идей
                    ideas.update(status=new_status)
                    messages.success(
                        request, f"✅ Статус изменен на «{new_status}» для {ideas.count()} идей."
                    )
                else:
                    messages.warning(request, "⚠️ Не выбран новый статус.")
        else:
            messages.warning(request, "⚠️ Вы не выбрали ни одной идеи.")

        return redirect("topics:dashboard")

    # Статистика (без изменений)
    stats = {
        "total": VideoProject.objects.count(),
        "new": VideoProject.objects.filter(status="new").count(),
        "pending": VideoProject.objects.filter(status="pending").count(),
        "done": VideoProject.objects.filter(status="completed").count(),
    }

    # Список последних идей (без изменений)
    ideas = VideoProject.objects.all().order_by("-created_at")[:50]

    # --- НАСТРОЙКА ПАГИНАЦИИ (без изменений) ---
    page_number = request.GET.get("page", 1)
    paginator = Paginator(ideas, 20)

    try:
        ideas_page = paginator.page(page_number)
    except PageNotAnInteger:
        ideas_page = paginator.page(1)
    except EmptyPage:
        ideas_page = paginator.page(paginator.num_pages)

    # --- ДОБАВЛЕНО: РАСЧЕТ ОБРАТНОЙ НУМЕРАЦИИ ---
    total_count = ideas.count()  # Общее количество идей
    per_page = 20  # Количество на странице

    # Номер первой идеи на этой странице (с конца)
    start_num = total_count - ((ideas_page.number - 1) * per_page)

    # Номер последней идеи на этой странице
    count_on_page = len(ideas_page.object_list)
    end_num = start_num - count_on_page + 1

    # Защита от нуля или отрицательных чисел
    if total_count == 0:
        start_num = 0
        end_num = 0

    # ГЕНЕРАЦИЯ СПИСКА НОМЕРОВ (70, 69, 68...)
    row_numbers = range(start_num, end_num - 1, -1)

    # СОЕДИНЕНИЕ ИДЕЙ С НОМЕРАМИ
    ideas_with_numbers = zip(ideas_page.object_list, row_numbers)

    context = {
        "stats": stats,
        "ideas_with_numbers": ideas_with_numbers,
        "page_obj": ideas_page,
        "total_count": total_count,
        "start_num": start_num,
        "end_num": end_num,
    }
    return render(request, "topics/dashboard.html", context)


def project_edit(request, pk):
    # Получаем проект или 404
    project = get_object_or_404(VideoProject, pk=pk)

    if request.method == "POST":
        form = VideoProjectEditForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Идеи успешно сохранены!")
            # Перезагружаем страницу, чтобы увидеть изменения
            return redirect("topics:project_edit", pk=pk)
        else:
            messages.error(request, "❌ Ошибка при сохранении. Проверьте поля.")
    else:
        # Если GET запрос, просто создаем форму с текущими данными
        form = VideoProjectEditForm(instance=project)

    context = {"form": form, "project": project}
    return render(request, "topics/project_edit.html", context)
