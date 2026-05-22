import json
import uuid
import threading
import time
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection

# Импортируем модели из твоих рабочих аппов
from audio.models import AudioProject, AudioTrack
from image.models import ImageProject, ImagePrompt
# Предположим, модель для хранения результатов рендеринга мы назовем VideoRender
# Если ты её еще не создавал, пока можно закомментировать строку ниже
# from .models import VideoRender


@login_required
def video_editor_view(request, project_id):
    """
    Интерфейс видеоредактора: сборка таймлайна + фоновый рендеринг видео.
    """
    # Достаем проект аудио (главный ориентир)
    audio_project = get_object_or_404(AudioProject, id=project_id, user=request.user)

    # 2. ПОИСК КАРТИНОК ПО НАЗВАНИЮ (Самый надежный способ в нашей структуре)
    # Отрезаем лишние пробелы и ищем проект картинок с похожим названием
    clean_title = audio_project.title.strip()

    image_project = ImageProject.objects.filter(title__icontains=clean_title).first()

    # План Б: Если по имени не нашли, пробуем старый метод через статью (если она заполнена)
    if not image_project and audio_project.article:
        image_project = ImageProject.objects.filter(article_id=audio_project.article_id).first()

    # 3. Собираем данные для таймлайна (сопоставляем по полю order)
    tracks = AudioTrack.objects.filter(project=audio_project).order_by("order")

    # Вытаскиваем промпты (кадры), если проект картинок был найден
    prompts = []
    if image_project:
        prompts = ImagePrompt.objects.filter(project=image_project).order_by("order")
        print(
            f"📸 Найдено кадров для таймлайна: {prompts.count()} (Из проекта картинок ID: {image_project.id})"
        )
    else:
        print(
            f"⚠️ Предупреждение: Не удалось найти связанный проект картинок по имени '{clean_title}'"
        )

    # 4. Упаковываем в единую ленту (timeline) для шаблона
    timeline_data = []

    # За основу берем треки озвучки
    for track in tracks:
        # Ищем соответствующий кадр с таким же order
        # Используем старый добрый Python-генератор
        prompt = next((p for p in prompts if p.order == track.order), None)

        # ДЕБАГ-ПРИНТ: Проверим в консоли, склеился ли кадр с аудио
        if prompt:
            print(f"🔗 Склейка таймлайна: Трек #{track.order} успешно нашел кадр #{prompt.order}")
        else:
            print(
                f"❓ Трек #{track.order} остался без картинки (Промпт с order={track.order} не найден)"
            )

        timeline_data.append({"order": track.order, "track": track, "prompt": prompt})

    # Проверяем, есть ли уже готовый отрендеренный ролик в базе
    # (Пока завязано на заглушку, если модель VideoRender еще не создана)
    video_render = None
    # try:
    #     video_render = audio_project.video_render
    # except:
    #     pass

    # =========================================================================
    # AJAX-ОБРАБОТЧИК: Прогресс-бар и запуск генерации
    # =========================================================================
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # 1. Проверка прогресса (GET) — твоя стандартная логика
        if request.method == "GET":
            task_id = request.GET.get("task_id")
            progress = cache.get(f"progress_{task_id}") or cache.get(f"gen_progress_{task_id}")
            if progress:
                return JsonResponse(progress)
            return JsonResponse({"completed": True, "percent": 100, "success": True})

        # 2. Запуск сборки видеоролика (POST)
        if request.method == "POST":
            try:
                data = json.loads(request.body)
            except:
                data = {}

            if data.get("action") != "start_render":
                return JsonResponse({"success": False, "error": "Неверное действие"}, status=400)

            # Проверяем, что есть материалы для сборки
            if not timeline_data:
                return JsonResponse(
                    {"success": False, "error": "Нет материалов для сборки видео"}, status=400
                )

            task_id = str(uuid.uuid4())

            # Инициализируем начальный статус рендеринга в кэше Django
            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 5,
                    "message": "🎬 Анализ дорожек таймлайна и подготовка FFmpeg...",
                    "status": "running",
                    "task_id": task_id,
                    "total_count": len(timeline_data),
                    "completed_count": 0,
                },
                timeout=3600,
            )

            # ФОНОВАЯ ФУНКЦИЯ РЕНДЕРИНГА
            def run_video_assembly():
                try:
                    total_scenes = len(timeline_data)

                    # Имитируем шаги склейки сцен для проверки интерфейса
                    # Позже мы заменим этот цикл на реальный вызов moviepy / ffmpeg
                    for i, item in enumerate(timeline_data):
                        current_num = i + 1

                        # Расчет процентов прогресса
                        percent = int((i / total_scenes) * 90) + 5

                        # Обновляем состояние в кэше для фронтенда
                        data = cache.get(f"progress_{task_id}", {})
                        if data:
                            data["percent"] = percent
                            data["message"] = (
                                f"📹 Склеиваем сцену {current_num} из {total_scenes} (Кадр + Аудио)..."
                            )
                            data["completed_count"] = i
                            cache.set(f"progress_{task_id}", data, timeout=3600)

                        # Пауза-имитация тяжелой склейки кадра
                        time.sleep(3)

                    # Финализация: Сборка завершена успешно
                    cache.set(
                        f"progress_{task_id}",
                        {
                            "percent": 100,
                            "message": "✅ Видеоролик успешно собран и сохранен!",
                            "status": "done",
                            "task_id": task_id,
                            "completed": True,
                        },
                        timeout=3600,
                    )

                except Exception as e:
                    cache.set(
                        f"progress_{task_id}",
                        {
                            "status": "error",
                            "message": f"Ошибка сборки видео: {str(e)}",
                            "percent": 0,
                        },
                        timeout=3600,
                    )
                finally:
                    connection.close()

            # Запускаем фоновый поток, чтобы страница не висла
            threading.Thread(target=run_video_assembly, daemon=True).start()
            return JsonResponse({"success": True, "task_id": task_id})

    # ОБЫЧНЫЙ GET-ЗАПРОС: Рендерим страницу редактора
    return render(
        request,
        "videoeditor/video_editor.html",  # Папку шаблонов внутри приложения назови videoeditor
        {
            "project": audio_project,
            "timeline_data": timeline_data,
            "video_render": video_render,
        },
    )
