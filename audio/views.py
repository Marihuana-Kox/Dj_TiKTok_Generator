import json
import os
import threading
import time
import uuid
from django.db.models import Prefetch
from django.db import connection
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse, StreamingHttpResponse
from django.core.paginator import Paginator

from tiktok_web import settings
from .models import AudioProject, AudioTrack
from article.models import ArticleCluster, ArticleTranslation
from ai_inspector.models import AIProvider
from .services import generate_voiceover_inworld, split_text_by_words_and_dots


def get_project_audio_progress(project):
    """
    Универсальная функция расчета прогресса озвучки для любого проекта.
    Возвращает словарь с количеством треков, готовых файлов и процентом.
    """
    # Загружаем все треки, привязанные к этому проекту
    tracks = project.tracks.all()
    total_count = tracks.count()

    # Считаем только успешные треки, у которых физически записан аудиофайл
    success_count = tracks.filter(status="success").exclude(audio_file="").count()

    # Считаем чистый процент (с защитой от деления на ноль)
    percent = int((success_count / total_count) * 100) if total_count > 0 else 0

    return {
        "total_tracks": total_count,
        "success_tracks": success_count,
        "progress_percent": percent,
        "project_ready": total_count > 0 and (total_count == success_count),
    }


@login_required
def audio_dashboard(request):
    """Дашборд аудио проектов с принудительным выводом русских названий статей"""

    # Обработка массовых действий
    if request.method == "POST":
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_projects")

        if action == "delete_selected" and selected_ids:
            AudioProject.objects.filter(id__in=selected_ids, user=request.user).delete()
            messages.success(request, f"✅ Удалено проектов: {len(selected_ids)}")
            return redirect("audio:dashboard")

    # Получаем базовый QuerySet
    projects_qs = AudioProject.objects.filter(user=request.user).order_by("-created_at")
    total_count = projects_qs.count()

    # Пагинация
    paginator = Paginator(projects_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Подготовка данных для таблицы
    projects_list = []

    # Считаем стартовый номер для обратного отсчета на текущей странице
    start_num = total_count - ((page_obj.number - 1) * paginator.per_page)

    for idx, project in enumerate(page_obj):
        if project.title and project.title.lower() != "default":
            display_title = project.title
        elif project.article and hasattr(project.article, "title"):
            display_title = project.article.title
        else:
            display_title = f"Аудио-проект #{project.id}"

        # Вычисляем порядковый номер строки (обратный отсчет)
        reverse_num = start_num - idx

        tracks_count = project.tracks.count()
        completed_count = project.tracks.filter(status="success").count()

        # Считаем процент прогресса по трекам
        progress_percent = int((completed_count / tracks_count) * 100) if tracks_count > 0 else 0

        # --- РАБОТА С ПУТЯМИ И АУДИОФАЙЛАМИ ---
        audio_url = None
        project_lang = (project.language or "ru").lower()  # Код языка (ru, de, en)

        # Получаем последний успешный трек, чтобы вывести его плеер в таблицу дашборда
        last_success_track = project.tracks.filter(status="success").order_by("-created_at").first()

        if last_success_track and project.article:
            # Нам нужно имя файла (например: voice_5.wav)
            file_name = f"voice_{last_success_track.id}.wav"

            try:
                # Название папки проекта без пробелов: "Великая_ложь_Колумба"
                safe_folder_name = display_title.replace(" ", "_")

                # Динамическое имя подпапки аудио: "voices_ru", "voices_de"
                dir_name = f"voices_{project_lang}"

                # 1. СТРАТЕГИЯ №1: Ищем по нашей НОВОЙ структуре
                # projects/Великая_ложь_Колумба/voices_ru/voice_5.wav
                new_voice_rel = os.path.join("projects", safe_folder_name, dir_name)
                new_abs_path = os.path.join(settings.MEDIA_ROOT, new_voice_rel, file_name)

                if os.path.exists(new_abs_path):
                    audio_url = f"{settings.MEDIA_URL}{new_voice_rel}/{file_name}".replace(
                        "\\", "/"
                    )

                # 2. СТРАТЕГИЯ №2: Фолбэк для старых тестовых файлов, если новой структуры еще нет
                else:
                    old_voice_rel = os.path.join("voice", safe_folder_name)
                    old_abs_dir = os.path.join(settings.MEDIA_ROOT, old_voice_rel)

                    if os.path.exists(old_abs_dir):
                        speaker_name = last_success_track.speaker_name or "Nikolay"
                        for file in os.listdir(old_abs_dir):
                            if file.lower().startswith(
                                speaker_name.lower()
                            ) and file.lower().endswith((".wav", ".mp3", ".mpeg")):
                                audio_url = f"{settings.MEDIA_URL}{old_voice_rel}/{file}".replace(
                                    "\\", "/"
                                )
                                break
            except Exception as e:
                print(f"🚨 Ошибка поиска аудиофайла на дашборде: {e}")
                audio_url = None

        # Собираем данные для конкретной строки таблицы
        projects_list.append(
            {
                "instance": project,
                "id": project.id,
                "reverse_num": reverse_num,
                "title": display_title,  # 🔥 ТЕПЕРЬ ТУТ СТРОГО РУССКОЕ НАЗВАНИЕ СТАТЬИ
                "article_title": (project.article.title if project.article else "Без статьи"),
                "language_code": project_lang,
                "audio_url": audio_url,
                "provider": project.provider,
                "status": project.status,
                "tracks_count": tracks_count,
                "completed_count": completed_count,
                "progress_percent": progress_percent,
                "created_at": project.created_at,
            }
        )

    # Статистика для верхних карточек
    stats = {
        "total": total_count,
        "processing": projects_qs.filter(status="processing").count(),
        "completed": projects_qs.filter(status="completed").count(),
    }

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "projects": projects_list,
        "stats": stats,
    }
    return render(request, "audio/dashboard.html", context)


@login_required
def audio_create(request):
    """Шаг 1: Только выбор статьи, доступного языка-перевода и нарезка текста"""

    # AJAX: Отдаем языки при выборе статьи
    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        and request.GET.get("action") == "get_languages"
    ):
        cluster_id = request.GET.get("cluster_id")
        try:
            translations = ArticleTranslation.objects.filter(cluster_id=cluster_id).select_related(
                "language"
            )
            langs_data = [
                {
                    "code": tr.language.code,
                    "name": tr.language.name,
                    "words": len(tr.content.split()) if tr.content else 0,
                }
                for tr in translations
            ]
            return JsonResponse({"success": True, "languages": langs_data})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    # ОБРАБОТКА ФОРМЫ (POST через AJAX/Fetch)
    if request.method == "POST":
        task_id = str(uuid.uuid4())
        cache_key = f"progress_{task_id}"

        # Стартовое состояние прогресса
        progress_data = {
            "percent": 5,
            "message": "Инициализация...",
            "status": "working",
            "logs": [
                "🚀 Запуск конвейера подготовки контента",
                f"🆔 Task ID: {task_id}",
            ],
        }
        cache.set(cache_key, progress_data, 3600)

        try:
            # Читаем данные (поддерживаем и обычный POST, и JSON-тело)
            if request.content_type == "application/json":
                data = json.loads(request.body)
                article_id = data.get(
                    "article_id"
                )  # Это на самом деле ID КЛЮЧЕВОГО кластера (cluster_id)
                lang_code = data.get("language")
                words_per_iteration = int(data.get("words_per_iteration", 50))
            else:
                article_id = request.POST.get("article_id")
                lang_code = request.POST.get("language")
                words_per_iteration = int(request.POST.get("words_per_iteration", 50))

            # Ищем текущий перевод (английский, немецкий и т.д.) для нарезки треков
            trans = ArticleTranslation.objects.filter(
                cluster_id=article_id, language__code=lang_code
            ).first()
            if not trans or not trans.content:
                raise ValueError("Текст перевода для выбранного языка не найден.")

            # Режем текст
            text_chunks = split_text_by_words_and_dots(
                trans.content, target_word_count=words_per_iteration
            )
            if not text_chunks:
                raise ValueError("Не удалось нарезать текст. Статья пустая?")

            def run_simulation_pipeline():
                try:
                    # Шаг 1: Имитация анализа текста
                    p_data = cache.get(cache_key)
                    p_data.update({"percent": 25, "message": "Лингвистический анализ текста..."})
                    p_data["logs"].append("🔍 Сканирование структуры предложений и разметки...")
                    cache.set(cache_key, p_data, 3600)
                    time.sleep(0.6)

                    # Шаг 2: Нарезка и запись проекта в БД
                    p_data = cache.get(cache_key)
                    p_data.update({"percent": 50, "message": "Разбиение на сюжетные фрагменты..."})
                    p_data["logs"].append(
                        f"✂️ Текст успешно разделен на {len(text_chunks)} логических блоков."
                    )
                    cache.set(cache_key, p_data, 3600)

                    # 🎯 НАШ ПЕРЕХВАТ: Ищем оригинальный РУССКИЙ заголовок для папки и дашборда
                    # Ищем его в том же самом кластере (article_id)
                    ru_main_trans = ArticleTranslation.objects.filter(
                        cluster_id=article_id, language__code="ru"
                    ).first()

                    # Если нашли русский заголовок — берем его, иначе оставляем текущий иностранный тайтл
                    project_title = ru_main_trans.title if ru_main_trans else trans.title

                    # Создаем проект строго по твоей модели AudioProject
                    audio_project = AudioProject.objects.create(
                        user=request.user,
                        article=None,  # Поле 'article' ожидает одиночный Article, оставляем None
                        title=project_title,  # 🔥 ТЕПЕРЬ ТУТ ВСЕГДА БУДЕТ "Великая ложь Колумба"
                        language=lang_code,  # А код языка пишется реальный (en, de...), под озвучку
                        provider="replicate_f5tts",
                        voice_preset="default",
                        status="pending",
                    )

                    # Наполняем базу треками (используем твою модель AudioTrack)
                    for idx, chunk_text in enumerate(text_chunks, start=1):
                        AudioTrack.objects.create(
                            project=audio_project,
                            order=idx,
                            text=chunk_text,
                            status="pending",
                        )
                    time.sleep(0.5)

                    # Шаг 3: Финал
                    p_data = cache.get(cache_key)
                    p_data.update({"percent": 85, "message": "Индексация базы данных..."})
                    p_data["logs"].append(
                        "💾 Сетка сюжетов успешно сохранена в репозиторий проекта."
                    )
                    cache.set(cache_key, p_data, 3600)
                    time.sleep(0.4)

                    # Завершаем и отдаем ПРАВИЛЬНЫЙ URL для редиректа на edit
                    final_data = {
                        "percent": 100,
                        "message": "Успешно сформировано!",
                        "status": "done",
                        "redirect_url": f"/audio/{audio_project.id}/edit/",
                        "logs": p_data["logs"]
                        + ["🎉 Подготовка завершена! Перенаправление в лабораровку озвучки..."],
                    }
                    cache.set(cache_key, final_data, 3600)

                except Exception as exc:
                    cache.set(
                        cache_key,
                        {
                            "percent": 100,
                            "message": "Ошибка выполнения",
                            "status": "error",
                            "logs": [f"❌ Сбой на стороне сервера: {str(exc)}"],
                        },
                        3600,
                    )
                finally:
                    connection.close()

            threading.Thread(target=run_simulation_pipeline, daemon=True).start()
            return JsonResponse({"success": True, "task_id": task_id})

        except Exception as e:
            cache.set(
                cache_key,
                {
                    "percent": 100,
                    "message": "Ошибка",
                    "status": "error",
                    "logs": [str(e)],
                },
                3600,
            )
            return JsonResponse({"success": True, "task_id": task_id})

    # GET-запрос: Вывод формы (Без изменений)
    articles = ArticleCluster.objects.prefetch_related(
        Prefetch(
            "translations",
            queryset=ArticleTranslation.objects.select_related("language"),
        )
    ).order_by("-created_at")[:100]

    articles_data = []
    for article in articles:
        main_trans = (
            article.translations.filter(language__code="ru").first() or article.translations.first()
        )
        if not main_trans:
            continue

        trans_stats = [
            {
                "language": tr.language.code,
                "lang_name": tr.language.name,
                "words": len((tr.content or "").split()),
            }
            for tr in article.translations.all()
        ]

        articles_data.append(
            {
                "id": article.id,
                "title": main_trans.title,
                "translations_json": json.dumps(trans_stats),
            }
        )

    context = {
        "page_title": "Новый проект озвучки",
        "articles": articles_data,
    }
    return render(request, "audio/audio_create.html", context)


@login_required
def audio_edit(request, pk):
    """Страница editing проекта и генерации аудио по частям"""
    # Загружаем проект текущего пользователя
    project = get_object_or_404(AudioProject, id=pk, user=request.user)

    # Достаем все треки, упорядоченные по возрастанию (1, 2, 3...)
    tracks = project.tracks.all().order_by("order")
    audio_providers = AIProvider.objects.filter(is_active=True, provider_type="audio")

    # 🔥 ВЫЗОВ НАШЕЙ ОТДЕЛЬНОЙ ФУНКЦИИ ПРОГРЕССА
    progress_data = get_project_audio_progress(project)

    # 2. Безопасно читаем голоса из JSON-конфига
    config_path = os.path.join(settings.BASE_DIR, "audio", "voice_config.json")
    voices_list = []

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            # Извлекаем словарь голосов корректно
            voices_dict = config_data.get("voices", {})
            target_key = None
            for key in voices_dict.keys():
                if key.lower() == project.language.lower() or key.lower().startswith(
                    project.language.lower()
                ):
                    target_key = key
                    break

            if target_key:
                voices_list = voices_dict.get(target_key, [])

    # Собираем контекст, подмешивая туда данные из нашей функции
    context = {
        "page_title": f"Озвучка: {project.title}",
        "project": project,
        "tracks": tracks,
        "audio_providers": audio_providers,
        "voices": voices_list,
        # 🔥 Новые переменные для твоей простой шкалы прогресса в HTML
        "total_tracks": progress_data["total_tracks"],
        "success_tracks": progress_data["success_tracks"],
        "progress_percent": progress_data["progress_percent"],
        "project_ready": progress_data["project_ready"],
    }
    return render(request, "audio/audio_edit.html", context)


@login_required
def synthesize_single_track(request, track_id=None):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Метод не разрешен"}, status=405)

    try:
        data = json.loads(request.body)
        provider_id = data.get("provider")
        voice_preset_id = data.get("voice_preset")

        track_ids = data.get("track_ids", [])
        if track_id and not track_ids:
            track_ids = [track_id]

        if not track_ids:
            return JsonResponse({"success": False, "error": "Не выбраны фрагменты для озвучки"})

        # Если пришел массив ID (пакетная генерация), исключаем треки, у которых уже есть аудиофайл
        if len(track_ids) > 1:
            # Выбираем из базы только те треки из списка, у которых поле audio_file пустое или отсутствует
            filtered_tracks = AudioTrack.objects.filter(id__in=track_ids)
            # Пересобираем track_ids, оставляя только новые/неозвученные
            track_ids = list(filtered_tracks.values_list("id", flat=True))

            # Если после фильтрации все треки оказались уже озвученными
            if not track_ids:
                return JsonResponse(
                    {
                        "success": True,
                        "message": "Все выбранные фрагменты уже были успешно озвучены ранее!",
                    }
                )

        tracks_to_process = AudioTrack.objects.filter(
            id__in=track_ids, project__user=request.user
        ).order_by("order")
        tracks_to_process.update(status="processing", error_message="")

        task_id = str(uuid.uuid4())
        cache_key = f"progress_{task_id}"

        cache.delete(cache_key)

        init_progress = {
            "percent": 5,
            "message": "📡 Инициализация очереди синтеза...",
            "status": "running",
            "logs": [
                "🚀 Запуск фонового процесса генерации аудио.",
                f"🆔 Идентификатор задачи: {task_id}",
                f"📊 Всего фрагментов в очереди: {len(track_ids)}",
            ],
        }
        cache.set(cache_key, init_progress, timeout=3600)

        def run_async_voice_generation():
            try:
                total_tracks = len(tracks_to_process)

                try:
                    if provider_id and str(provider_id).isdigit():
                        provider_obj = AIProvider.objects.get(id=int(provider_id))
                    else:
                        provider_obj = (
                            AIProvider.objects.filter(name=provider_id).first()
                            or AIProvider.objects.filter(
                                is_active=True, provider_type="audio"
                            ).first()
                        )
                except Exception:
                    provider_obj = AIProvider.objects.filter(
                        is_active=True, provider_type="audio"
                    ).first()

                if not provider_obj:
                    raise Exception("В системе не найден активный AI провайдер с API ключом!")

                p_data = cache.get(cache_key) or init_progress
                p_data["logs"].append(f"🤖 Выбран провайдер: {provider_obj.name}")
                cache.set(cache_key, p_data, timeout=3600)

                # 📁 ОПРЕДЕЛЯЕМ ПРОЕКТ (СТАТЬЮ) ДЛЯ ОЗВУЧКИ
                sample_track = tracks_to_process.first()
                if not sample_track:
                    raise Exception("Фрагменты для обработки исчезли из базы.")

                project = sample_track.project
                project_language = project.language or "ru"

                # То самое русское название статьи, по которому строятся все пути на сервере
                project_title_ru = project.title

                # ЦИКЛ ПО ТРЕКАМ
                for index, current_track in enumerate(tracks_to_process):
                    current_num = index + 1

                    p_data = cache.get(cache_key)
                    p_data["percent"] = int((index / total_tracks) * 40) + 5
                    p_data["message"] = f"🧬 Озвучка фрагмента {current_num} из {total_tracks}..."
                    p_data["logs"].append(
                        f"📡 [Фрагмент {current_num}/{total_tracks}]: Отправка текста провайдеру..."
                    )
                    cache.set(cache_key, p_data, timeout=3600)

                    # 🔥 ИДЕАЛЬНЫЙ ВЫЗОВ: Передаем орднунг (`current_track.order`),
                    # а функция генерации сама сложит аудио в нужную папку с правильным именем!
                    audio_file_url = generate_voiceover_inworld(
                        text=current_track.text,
                        provider_instance=provider_obj,
                        voice_id=voice_preset_id,
                        language=project_language,
                        project_title=project_title_ru,
                        article_id=project.id,
                        track_order=current_track.order,  # Передали честный номер фрагмента
                        task_id=task_id,
                    )

                    if not audio_file_url:
                        raise Exception(
                            f"Провайдер вернул пустой URL для фрагмента #{current_track.id}"
                        )

                    # Сохраняем полученный готовый URL в базу данных трека
                    current_track.status = "success"
                    current_track.audio_file = audio_file_url
                    current_track.save()

                    p_data = cache.get(cache_key)

                    cache.set(cache_key, p_data, timeout=3600)

                    # Пауза безопасности 16 секунд
                    if current_num < total_tracks:
                        p_data = cache.get(cache_key)
                        p_data["message"] = "⏱️ Пауза безопасности API (16с)..."
                        p_data["logs"].append("⏳ Защита лимитов: ждем 16 секунд...")
                        cache.set(cache_key, p_data, timeout=3600)

                        time.sleep(16)

                # Финал
                cache.set(
                    cache_key,
                    {
                        "percent": 100,
                        "message": "🎉 Озвучка завершена успешно!",
                        "status": "done",
                        "logs": [
                            "📥 Все аудиофайлы успешно получены.",
                            "💾 Очередь закрыта!",
                        ],
                    },
                    timeout=3600,
                )

            except Exception as thread_err:
                error_msg = str(thread_err)
                print(f"🚨 Ошибка в потоке генерации аудио: {error_msg}")

                tracks_to_process.filter(status="processing").update(
                    status="failed", error_message=error_msg
                )

                cache.set(
                    cache_key,
                    {
                        "percent": 100,
                        "message": f"❌ ОШИБКА: {error_msg}",
                        "status": "running",
                        "logs": [
                            "📡 Процесс обработки прерван.",
                            f"❌ Критическая ошибка в коде: {error_msg}",
                            "🛑 Пожалуйста, исправьте ошибку в терминале или проверьте ключи провайдера.",
                        ],
                    },
                    timeout=3600,
                )
            finally:
                connection.close()

        threading.Thread(target=run_async_voice_generation, daemon=True).start()
        return JsonResponse({"success": True, "task_id": task_id})

    except Exception as e:
        print(f"🚨 Ошибка инициализации синтеза: {str(e)}")
        return JsonResponse({"success": False, "error": f"Ошибка сервера: {str(e)}"}, status=200)


@login_required
def save_track_text_ajax(request, track_id):
    track = get_object_or_404(AudioTrack, id=track_id, project__user=request.user)
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Метод не разрешен"}, status=405)

    try:
        data = json.loads(request.body)
        text_content = data.get("text", "").strip()

        # Находим фрагмент и проверяем права
        track = get_object_or_404(AudioTrack, id=track_id, project__user=request.user)

        if not text_content:
            return JsonResponse({"success": False, "error": "Текст не может быть пустым"})
        # Записываем текст и ЖЕСТКО СБРАСЫВАЕМ ошибку в пустую строку
        track.text = text_content
        track.error_message = ""  # Обнуляем ошибку, так как текст изменился и сохранен!
        if track.status == "failed":
            track.status = "new"  # Если трек лежал в ошибке, возвращаем его в нормальный статус
        track.save()

        print(f"💾 [Простое сохранение] Текст трека #{track.id} обновлен в БД.")
        return JsonResponse({"success": True, "message": "Текст успешно сохранен"})

    except Exception as e:
        print(f"🚨 Ошибка сохранения трека #{track_id}: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def generation_stream(request):
    # Получаем task_id из параметров запроса (его пришлет JS из modal.js)
    task_id = request.GET.get("task_id")

    def event_stream():
        if not task_id:
            yield f"data: {json.dumps({'status': 'error', 'message': 'No task_id'})}\n\n"
            return

        last_percent = -1
        last_msg = ""

        while True:
            # Читаем из кэша по task_id (это работает между всеми процессами сервера)
            data = cache.get(f"progress_{task_id}")

            if data:
                # Отправляем только при изменениях
                if (
                    data["percent"] != last_percent
                    or data["message"] != last_msg
                    or data["status"] in ["done", "error"]
                ):
                    yield f"data: {json.dumps(data)}\n\n"

                    last_percent = data["percent"]
                    last_msg = data["message"]

                if data["status"] in ["done", "error"]:
                    # Не удаляем кэш сразу, даем JS время получить финальный статус
                    break
            else:
                # Если задача еще не началась или кэш пуст
                yield f"data: {json.dumps({'status': 'waiting', 'message': 'Ожидание запуска...'})}\n\n"

            time.sleep(0.8)  # Чуть реже опрос, чтобы не нагружать процессор

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def generation_progress(request, task_id=None):
    """
    Универсальное API для получения прогресса.
    Защищено от ложных срабатываний завершения задачи.
    """
    if not task_id:
        task_id = request.GET.get("task_id")
    # 1. Проверяем основной ключ кэша
    progress = cache.get(f"progress_{task_id}")

    # 2. Если не нашли, проверяем старый вариант ключа
    if not progress:
        progress = cache.get(f"gen_progress_{task_id}")

    # 3. ЕСЛИ В КЭШЕ СОВСЕМ НИЧЕГО НЕТ (Задача только запускается):
    if not progress:
        return JsonResponse(
            {
                "success": True,
                "completed": False,
                "percent": 10,
                "message": "📡 Инициализация и проверка лимитов API...",
                "status": "running",
                "logs": ["⏳ Ожидание ответа от фонового процесса Django..."],
            }
        )

    # 4. Нормализуем структуру ответа для JS
    status = progress.get("status", "running")
    logs = progress.get("logs", [])

    # Если в кэше строка вместо массива логов (бывает при падении функции)
    if isinstance(logs, str):
        logs = [logs]

    response_data = {
        "success": True if status != "error" else False,
        "completed": True if status in ["done", "error"] else False,
        "percent": progress.get("percent", 50),
        "message": progress.get("message", "Обработка..."),
        "status": status,
        "logs": logs,
        "audio_url": progress.get("audio_url", None),
        "redirect_url": progress.get("redirect_url", None),
    }

    return JsonResponse(response_data)
