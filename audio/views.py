import json
import re
import time
import uuid
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse, StreamingHttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator

from tiktok_web import settings
from .models import AudioProject, AudioTrack
from article.models import Article, ArticleCluster, ArticleTranslation
from ai_inspector.models import AIProvider
from .services import generate_voiceover_inworld


@login_required
def audio_dashboard(request):
    """Дашборд аудио проектов"""
    projects_qs = AudioProject.objects.filter(user=request.user).order_by("-created_at")

    # Пагинация
    paginator = Paginator(projects_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Подготовка данных для таблицы
    projects_list = []
    for idx, project in enumerate(page_obj):
        tracks_count = project.tracks.count()
        completed_count = project.tracks.filter(status="success").count()

        projects_list.append(
            {
                "instance": project,
                "id": project.id,
                "title": project.title,
                "article_title": (
                    project.article.title if project.article else "Без статьи"
                ),
                "provider": project.provider,
                "status": project.status,
                "tracks_count": tracks_count,
                "completed_count": completed_count,
                "created_at": project.created_at,
            }
        )

    # Обработка массовых действий
    if request.method == "POST":
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_projects")

        if action == "delete_selected" and selected_ids:
            AudioProject.objects.filter(id__in=selected_ids, user=request.user).delete()
            messages.success(request, f"✅ Удалено проектов: {len(selected_ids)}")
            return redirect("audio:dashboard")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "projects_list": projects_list,
    }
    return render(request, "audio/dashboard.html", context)


@login_required
def audio_create(request):
    # --- БЛОК 1: AJAX получение текста (для превью в JS) ---
    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        and request.GET.get("action") == "get_text"
    ):
        cluster_id = request.GET.get("cluster_id")
        lang_code = request.GET.get("lang")
        try:
            translation = ArticleTranslation.objects.get(
                cluster_id=cluster_id,
                language__code=lang_code,
            )
            full_text = getattr(translation, "content", "") or translation.title
            words = full_text.split()[:10]
            preview_text = " ".join(words)
            return JsonResponse({"success": True, "text": preview_text})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    # --- БЛОК 2: POST Обработка (Генерация) ---
    if request.method == "POST":
        task_id = str(uuid.uuid4())
        cache_key = f"progress_{task_id}"

        # МГНОВЕННЫЙ СТАРТ (Чтобы модалка сразу ожила)
        progress_data = {
            "percent": 5,
            "message": "Инициализация задачи...",
            "status": "working",
            "logs": ["🚀 Кнопка нажата", f"🆔 ID задачи: {task_id}"],
        }
        cache.set(cache_key, progress_data, 3600)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            try:
                data = json.loads(request.body)

                # --- [DEBUG ВЫВОД В ТЕРМИНАЛ] ---
                print(f"\n🎯 [POST RECEIVED] Task: {task_id}")
                print(f"📦 PAYLOAD: {json.dumps(data, indent=2, ensure_ascii=False)}")

                # 1. Извлекаем данные
                provider_id = data.get("provider_id")
                cluster_id = data.get("article_id")
                lang_full = data.get("language", "ru-RU")
                lang_code = lang_full.split("-")[0]  # 'ru-RU' -> 'ru'

                # 2. Пытаемся найти текст в БД, если его не прислал JS
                text_to_speak = data.get("text")
                if not text_to_speak:
                    # Если JS не прислал текст, бэкенд ищет его сам в ArticleTranslation
                    trans = ArticleTranslation.objects.filter(
                        cluster_id=cluster_id, language__code=lang_code
                    ).first()
                    if trans:
                        text_to_speak = trans.content
                        progress_data["logs"].append(
                            f"📑 Текст взят из БД (Кластер {cluster_id})"
                        )
                    else:
                        raise ValueError(f"Текст для языка {lang_code} не найден в БД")

                # 3. Проверка провайдера
                provider_instance = AIProvider.objects.filter(
                    name=provider_id, is_active=True
                ).first()
                if not provider_instance:
                    # Мы не возвращаем status=404, чтобы не сломать модалку, а пишем в логи
                    raise ValueError(f"Провайдер ID {provider_id} не найден")

                # 4. ВЫЗОВ СЕРВИСА (Обернут, чтобы не вешать сервер)
                try:
                    progress_data.update(
                        {
                            "percent": 40,
                            "message": "Отправка на API...",
                            "logs": progress_data["logs"]
                            + ["📡 Установка связи с провайдером..."],
                        }
                    )
                    cache.set(cache_key, progress_data, 3600)

                    # --- ТВОЯ ФУНКЦИЯ ГЕНЕРАЦИИ ---
                    audio_rel_path = generate_voiceover_inworld(
                        text=text_to_speak,
                        provider_instance=provider_instance,
                        voice_id=data.get("voice_id"),
                        language=lang_full,
                        speaking_rate=data.get("audio_config", {}).get(
                            "speaking_rate", 1.0
                        ),
                        folder_name=data.get("folder_name", "voiceover"),
                    )

                    # 5. Финализация успеха
                    final_data = {
                        "percent": 100,
                        "message": "Готово!",
                        "status": "done",
                        "redirect_url": f"{settings.MEDIA_URL}{audio_rel_path}",
                        "logs": progress_data["logs"]
                        + ["✅ Файл успешно создан и сохранен"],
                    }
                    cache.set(cache_key, final_data, 3600)

                except Exception as e:
                    # Ловим "стену" здесь
                    print(f"❌ API ERROR: {str(e)}")
                    error_data = {
                        "percent": 100,
                        "message": "Ошибка API",
                        "status": "error",
                        "logs": progress_data["logs"]
                        + [f"❌ Ошибка провайдера: {str(e)}"],
                    }
                    cache.set(cache_key, error_data, 3600)

                # Возвращаем успех ВСЕГДА, когда создан task_id, чтобы JS запустил модалку
                return JsonResponse(
                    {
                        "success": True,
                        "task_id": task_id,
                    }
                )

            except Exception as e:
                # Критическая ошибка (например, БД упала)
                print(f"💥 CRITICAL: {str(e)}")
                return JsonResponse({"success": False, "error": str(e)}, status=200)

    # --- БЛОК 3: GET Рендер (Подготовка контекста) ---
    providers = AIProvider.objects.filter(provider_type="audio", is_active=True)
    articles = ArticleCluster.objects.prefetch_related(
        Prefetch(
            "translations",
            queryset=ArticleTranslation.objects.only(
                "cluster_id", "language", "title", "content"
            ),
        )
    ).order_by("-created_at")[:50]

    articles_data = []
    for article in articles:
        main_trans = (
            article.translations.filter(language__code="ru").first()
            or article.translations.first()
        )
        display_title = main_trans.title if main_trans else f"Кластер #{article.id}"

        trans_stats = []
        for tr in article.translations.all():
            text = tr.content or tr.title or ""
            trans_stats.append(
                {
                    "language": tr.language.code,
                    "words": len(text.split()),
                    "chars": len(text),
                }
            )

        articles_data.append(
            {
                "id": article.id,
                "title": display_title,
                "translations": trans_stats,
                "translations_json": json.dumps(trans_stats),  # Сериализуем сразу
            }
        )

    language_all = [
        {"code": "ru-RU", "name": "Русский"},
        {"code": "en-US", "name": "English"},
        {"code": "de-DE", "name": "Deutsch"},
    ]

    # 4. Маппинг голосов по языкам (Полный список)
    voices = {
        "ru-RU": [
            {"id": "Dmitriy", "name": "Дмитрий (муж.)"},
            {"id": "Nikolai", "name": "Николай (муж.)"},
            {"id": "Elena", "name": "Елена (жен.)"},
            {"id": "Svetlana", "name": "Светлана (жен.)"},
        ],
        "en-US": [
            {"id": "Alex", "name": "Alex (male)"},
            {"id": "Anjali", "name": "Anjali (female)"},
        ],
        "de-DE": [
            {"id": "Josef", "name": "Josef (male)"},
            {"id": "Johanna", "name": "Johanna (female)"},
        ],
    }

    context = {
        "providers": providers,
        "articles": articles_data,
        "languages": json.dumps(language_all),
        "voices": voices,
        "page_title": "Новый проект озвучки",
    }
    return render(request, "audio/audio_create.html", context)


@login_required
def audio_edit(request, pk):
    """Редактирование аудио проекта"""
    project = get_object_or_404(AudioProject, id=pk, user=request.user)
    tracks = project.tracks.all().order_by("order")

    # Получаем audio-провайдеров
    audio_providers = AIProvider.objects.filter(is_active=True, provider_type="audio")

    # AJAX: генерация аудио
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if request.method == "POST":
            # Логика генерации (добавим позже)
            return JsonResponse({"success": True, "message": "Генерация запущена"})

    context = {
        "project": project,
        "tracks": tracks,
        "audio_providers": audio_providers,
    }
    return render(request, "audio/audio_edit.html", context)


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


def generation_progress(request, task_id):
    """
    Универсальное API для получения прогресса.
    Поддерживает и создание промптов, и генерацию картинок.
    """

    # Проверяем основной ключ (который мы используем сейчас)
    progress = cache.get(f"progress_{task_id}")

    # Если не нашли, проверяем старый вариант ключа (для подстраховки)
    if not progress:
        progress = cache.get(f"gen_progress_{task_id}")

    if not progress:
        # Если в кэше вообще ничего нет, значит задача либо не создана,
        # либо уже удалена из кэша. Возвращаем структуру, которая не сломает JS.
        return JsonResponse(
            {
                "completed": True,
                "percent": 100,
                "message": "Завершено или не найдено",
                "status": "done",
                "completed_count": 0,
                "total_count": 0,
            }
        )

    # Добавляем флаг завершения для JS, если статус 'done'
    if progress.get("status") == "done":
        progress["completed"] = True

    return JsonResponse(progress)
