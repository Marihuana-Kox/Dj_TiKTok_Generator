import json
import time
import threading
import uuid
from django.db import connection
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

# Импорт моделей
from prompts.models import ArticlePrompt
from shorts.progressbar import ProgressManager
from topics.models import VideoProject
from .models import ArticleCluster, ArticleTranslation, Language, VideoScript
from .forms import ArticleCreateForm, ArticleGenerationForm, VideoScriptForm

# Импорт сервисов
from ai_inspector.services import generate_text
from prompts.services import get_system_instruction


# Глобальное хранилище прогресса
ARTICLE_GEN_PROGRESS = {}
CACHE_TIMEOUT = 3600


def article_generate_page(request):
    form = ArticleGenerationForm()
    return render(request, "article/generate.html", {"form": form})


def start_generation_api(request):
    """API endpoint для запуска генерации через AJAX"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Метод не разрешен"}, status=405)

    form = ArticleGenerationForm(request.POST)
    if not form.is_valid():
        # Возвращаем ошибки формы сразу
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)

    # --- 1. ПОДГОТОВКА ДАННЫХ (Код выполняется) ---
    task_id = str(uuid.uuid4())
    cd = form.cleaned_data
    selected_ids = cd["idea_selection"]
    selected_lang_codes = cd["languages"]

    if "en" not in selected_lang_codes:
        selected_lang_codes.append("en")

    prompt_code = cd["article_prompt"]
    img_mode = cd["image_mode"]
    manual_count = cd.get("manual_scene_count", 5)
    aspect_ratio = cd["aspect_ratio"]
    art_style = cd["art_style"]
    provider = cd["ai_provider"]
    generate_prompts = "enable_prompts_toggle" in request.POST

    # Оценка шагов
    steps_per_idea = 2 + len(selected_lang_codes) + (2 if generate_prompts else 0)
    total_steps_estimate = len(selected_ids) * steps_per_idea

    # Записываем в кэш стартовое состояние
    cache.set(
        f"progress_{task_id}",
        {
            "percent": 1,
            "message": "Инициализация...",
            "status": "running",
            "logs": ["🚀 Запуск задачи..."],
            "task_id": task_id,
        },
        timeout=3600,
    )

    def run_task():
        def update_task_progress(percent, message, status="running", final=False):
            data = cache.get(f"progress_{task_id}", {})
            logs = data.get("logs", [])
            if message and (not logs or logs[-1] != message):
                logs.append(message)

            payload = {
                "percent": percent,
                "message": message,
                "status": status,
                "logs": logs[-15:],
                "task_id": task_id,
            }
            if final:
                payload["redirect_url"] = "/article/"
            cache.set(f"progress_{task_id}", payload, timeout=3600)

        current_step = 0
        try:
            # Получаем объекты языков (из твоей модели Language)
            languages_map = {
                lang.code: lang for lang in Language.objects.filter(code__in=selected_lang_codes)
            }

            for idea_id in selected_ids:
                try:
                    # VideoProject — это модель твоей идеи
                    idea = VideoProject.objects.get(id=idea_id)
                except VideoProject.DoesNotExist:
                    continue

                # У VideoProject используем 'angle' вместо 'title'
                display_name = idea.angle if idea.angle else f"Idea {idea_id}"

                update_task_progress(
                    int((current_step / total_steps_estimate) * 100),
                    f"📝 Начинаем работу над: {display_name[:30]}...",
                )

                # 1. Создаем Кластер (ArticleCluster)
                cluster = ArticleCluster.objects.create(source_idea=idea)

                # 2. Подготовка промпта для EN версии
                # Тема берется из idea.angle, доп. контекст из idea.notes (согласно твоему коду)
                topic_context = idea.angle
                additional_context = idea.notes if idea.notes else ""

                # Ищем промпт (ArticlePrompt)
                if prompt_code == "random":
                    selected_prompt_obj = (
                        ArticlePrompt.objects.filter(is_active=True).order_by("?").first()
                    )
                else:
                    selected_prompt_obj = ArticlePrompt.objects.filter(
                        code_name=prompt_code, is_active=True
                    ).first()

                if not selected_prompt_obj:
                    raise ValueError(f"Промпт '{prompt_code}' не найден в БД")

                # Рендерим промпт через твой сервис render_article_prompt
                # (Он принимает объект промпта, тему, язык и контекст)
                en_prompt_text = selected_prompt_obj.render(
                    topic=topic_context, language="English", old_context=additional_context
                )

                # 3. Генерация основной статьи (English)
                update_task_progress(
                    int((current_step / total_steps_estimate) * 100),
                    f"🤖 AI генерирует статью (EN)...",
                )

                en_content_raw = generate_text(provider, en_prompt_text, max_tokens=3000)
                en_data = parse_ai_json(en_content_raw)

                if not en_data or not en_data.get("content"):
                    raise ValueError("AI вернул пустой контент для основной статьи")

                # 4. Сохраняем английский перевод в кластер (ArticleTranslation)
                lang_en = languages_map.get("en")
                if lang_en:
                    ArticleTranslation.objects.create(
                        cluster=cluster,
                        language=lang_en,
                        title=en_data.get("title", display_name),
                        content=en_data.get("content", ""),
                        description=en_data.get("description", "")[:200],
                        hashtags=en_data.get("hashtags", ""),
                        status="draft",
                    )

                current_step += 1

                # 5. Переводы на остальные выбранные языки
                for code in selected_lang_codes:
                    if code == "en":
                        continue

                    lang_obj = languages_map.get(code)
                    if not lang_obj:
                        continue

                    update_task_progress(
                        int((current_step / total_steps_estimate) * 100),
                        f"🌍 Перевод на {lang_obj.name}...",
                    )

                    # Используем твой сервис get_system_instruction для перевода
                    context = {
                        "target_lang": lang_obj.name,
                        "original_title": en_data.get("title"),
                        "article_content": en_data["content"],
                    }
                    trans_prompt = get_system_instruction("translation_strict", context)

                    trans_raw = generate_text(provider, trans_prompt, max_tokens=2500)
                    trans_data = parse_ai_json(trans_raw)

                    ArticleTranslation.objects.create(
                        cluster=cluster,
                        language=lang_obj,
                        title=trans_data.get("title", en_data["title"]),
                        content=trans_data.get("content", en_data["content"]),
                        description=trans_data.get("description", ""),
                        hashtags=trans_data.get("hashtags", ""),
                        status="draft",
                    )
                    current_step += 1

                # Обновляем статус исходной идеи и кластера
                idea.status = "completed"
                idea.save()
                cluster.is_complete = True
                cluster.save()

            # Завершение
            update_task_progress(100, "✅ Готово! Статьи созданы.", status="done", final=True)

        except Exception as e:
            print(f"ОШИБКА ГЕНЕРАЦИИ: {e}")
            update_task_progress(0, f"Ошибка: {str(e)}", status="error")
        finally:
            connection.close()

    # --- 3. ЗАПУСК ПОТОКА ---
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    # --- 4. ОТВЕТ КЛИЕНТУ (Только теперь!) ---
    # Теперь JS получит task_id и тут же откроет модалку
    return JsonResponse({"status": "ok", "task_id": task_id})


def count_text_stats(text):
    """Просто считает слова и символы. Возвращает кортеж (слова, символы)."""
    if not text:
        return 0, 0
    words = len(text.split())
    chars = len(text)
    return words, chars


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


def clean_json_string(text):
    """
    Очищает текст от символов, ломающих JSON:
    1. Заменяет умные кавычки на обычные.
    2. Экранирует двойные кавычки внутри строки.
    3. Заменяет реальные переносы строк на \n.
    """
    if not text:
        return ""

    # 1. Замена умных кавычек и апострофов
    text = text.replace('"', '"')  # Левая двойная
    text = text.replace('"', '"')  # Правая двойная
    text = text.replace(
        """, "'")   # Левая одинарная
    text = text.replace(""",
        "'",
    )  # Правая одинарная (апостроф)
    text = text.replace("`", "'")  # Гравис

    # ВАЖНО: Мы НЕ делаем replace('\n', '\\n') здесь,
    # так как это сломает структуру JSON (переносы между полями).
    # Если модель вставила реальный перенос строки ВНУТРИ строкового значения,
    # это нарушает стандарт JSON, но многие парсеры это прощают.
    # Если будет ошибка, мы попробуем другой метод ниже.

    return text


def parse_ai_json(text):
    if not text:
        return {}

    # 1. Чистим от маркдауна (если есть)
    text = text.replace("```json", "").replace("```", "").strip()

    # 2. НАХОДИМ JSON (от первой { до последней })
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        print("❌ Нет JSON скобок")
        return {}

    # Вырезаем кусок
    json_str = text[start : end + 1]

    # 3. ГЛАВНЫЙ ТРЮК: Заменяем ВСЕ реальные переносы строк на пробелы.
    # Да, текст статьи станет одной длинной строкой без абзацев,
    # НО это гарантированно спасет от ошибки "Invalid control character".
    # Абзацы можно восстановить потом заменой двойных пробелов, если нужно,
    # но для начала главное — чтобы работало.
    json_str = json_str.replace("\n", " ").replace("\r", " ")

    # 4. Чистим кавычки (на всякий случай)
    json_str = json_str.replace('"', '"').replace('"', '"')

    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"❌ Ошибка JSON: {e}")
        # Если не вышло — возвращаем пустоту, чтобы код не падал
        return {}


def article_dashboard(request):
    # --- УДАЛЕНИЕ И СМЕНА СТАТУСА ---
    if request.method == "POST":
        action = request.POST.get("action")

        selected_ids = request.POST.getlist("selected_articles")

        if selected_ids:
            clusters = ArticleCluster.objects.filter(id__in=selected_ids)

            if action == "delete_selected":
                count, _ = clusters.delete()
                messages.success(request, f"✅ Удалено {count} статей.")

            elif action == "change_status":
                new_status = request.POST.get("new_status")
                if new_status:
                    is_complete_val = new_status == "published"
                    clusters.update(is_complete=is_complete_val)

                    status_text = "Опубликовано" if is_complete_val else "В работе"
                    messages.success(
                        request,
                        f"✅ Статус изменен на «{status_text}» для {clusters.count()} статей.",
                    )
                else:
                    messages.warning(request, "⚠️ Не выбран новый статус.")
        else:
            messages.warning(request, "⚠️ Вы не выбрали ни одной статьи.")

        return redirect("article:dashboard")

    # --- ПОДГОТОВКА ДАННЫХ ---
    clusters_qs = ArticleCluster.objects.all().order_by("-created_at")

    # --- НАСТРОЙКА ПАГИНАЦИИ ---
    page_number = request.GET.get("page", 1)
    per_page = 20
    paginator = Paginator(clusters_qs, per_page)

    try:
        articles_page = paginator.page(page_number)
    except PageNotAnInteger:
        articles_page = paginator.page(1)
    except EmptyPage:
        articles_page = paginator.page(paginator.num_pages)

    # --- РАСЧЕТ ОБРАТНОЙ НУМЕРАЦИИ ---
    total_count = clusters_qs.count()

    # Номер первой строки на этой странице (с конца)
    start_num = total_count - ((articles_page.number - 1) * per_page)

    # Номер последней строки
    count_on_page = len(articles_page.object_list)
    end_num = start_num - count_on_page + 1

    if total_count == 0:
        start_num = 0
        end_num = 0

    # Генерация списка номеров (например: 70, 69, ... 51)
    row_numbers = range(start_num, end_num - 1, -1)

    # --- ПОДГОТОВКА СПИСКА СТАТЕЙ (только для текущей страницы) ---
    prepared_clusters = []

    # Крутим цикл только по объектам на ТЕКУЩЕЙ странице
    for cluster in articles_page.object_list:
        try:
            translations = list(cluster.translations.all())
            main_trans = None
            for t in translations:
                if t.language.code == "ru":
                    main_trans = t
                    break
            if not main_trans and translations:
                main_trans = translations[0]

            prepared_clusters.append(
                {
                    "instance": cluster,
                    "translations": translations,
                    "main_trans": main_trans,
                }
            )
        except Exception as e:
            print(f"Ошибка кластера #{cluster.id}: {e}")

    # Объединяем статьи с номерами строк
    articles_with_numbers = zip(prepared_clusters, row_numbers)

    stats = {
        "total": total_count,
        "draft": clusters_qs.filter(is_complete=False).count(),
        "published": clusters_qs.filter(is_complete=True).count(),
    }
    context = {
        "stats": stats,
        "articles_with_numbers": articles_with_numbers,
        "page_obj": articles_page,
        "total_count": total_count,
        "start_num": start_num,
        "end_num": end_num,
    }
    return render(request, "article/dashboard.html", context)


def article_editor(request, pk):
    cluster = get_object_or_404(ArticleCluster, id=pk)
    translations = cluster.translations.all().order_by("language__order")
    # Получаем список языков, которые ещё не переведены
    translated_lang_ids = translations.values_list("language_id", flat=True)
    available_languages = (
        Language.objects.filter(is_active=True)
        .exclude(id__in=translated_lang_ids)
        .order_by("order")
    )

    # основной перевод
    main_trans = translations.filter(language__code="ru").first()
    if not main_trans:
        main_trans = translations.first()

    # POST
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_translation":
            trans_id = request.POST.get("translation_id")
            if trans_id:
                trans = get_object_or_404(ArticleTranslation, id=trans_id, cluster=cluster)
                trans.title = request.POST.get("title")
                trans.content = request.POST.get("content")
                trans.description = request.POST.get("description")
                trans.hashtags = request.POST.get("hashtags")
                trans.save()
                messages.success(request, "Сохранено!")
                return redirect("article:article_editor", pk=cluster.id)

        elif action == "update_cluster_status":
            cluster.is_complete = request.POST.get("is_complete") == "on"
            cluster.save()
            messages.success(request, "Статус обновлен!")
            return redirect("article:article_editor", pk=cluster.id)

    # 👉 ВОТ КЛЮЧЕВОЕ: добавляем счетчики прямо в объекты
    for t in translations:
        text = t.content or ""
        words, chars = count_text_stats(text)

        t.word_count = words
        t.char_count = chars

    context = {
        "cluster": cluster,
        "translations": translations,
        "main_trans": main_trans,
        "available_languages": available_languages,
    }

    return render(request, "article/editor.html", context)


# Самостоятельное добавле готовых статей для роликов
def article_create(request):
    """Создание новой статьи вручную."""
    if request.method == "POST":
        form = ArticleCreateForm(request.POST)

        if form.is_valid():
            language = form.cleaned_data["language"]

            # 1. Создаём кластер (контейнер для всех переводов)
            cluster = ArticleCluster.objects.create(
                is_complete=(form.cleaned_data["status"] == "published")
            )

            # 2. Создаём первый перевод
            ArticleTranslation.objects.create(
                cluster=cluster,
                language=language,
                title=form.cleaned_data["title"],
                description=form.cleaned_data.get("description", ""),
                content=form.cleaned_data["content"],
                hashtags=form.cleaned_data.get("hashtags", ""),
                status=form.cleaned_data["status"],
            )

            messages.success(
                request, f"✅ Статья '{form.cleaned_data['title']}' создана на {language.name}!"
            )
            return redirect("article:article_editor", pk=cluster.pk)
        else:
            messages.error(request, "⚠️ Проверьте форму на ошибки.")
    else:
        form = ArticleCreateForm()

    context = {"form": form}
    return render(request, "article/create.html", context)


# Перевод статей на разные языки
def ai_translate(request, cluster_id):
    """Быстрый перевод статьи через AI."""
    cluster = get_object_or_404(ArticleCluster, id=cluster_id)

    if request.method != "POST":
        messages.error(request, "⚠️ Метод не разрешён")
        return redirect("article:article_editor", pk=cluster_id)

    target_lang_id = request.POST.get("target_language")
    if not target_lang_id:
        messages.error(request, "⚠️ Выберите язык для перевода")
        return redirect("article:article_editor", pk=cluster_id)

    target_language = get_object_or_404(Language, id=target_lang_id)

    # Проверяем, нет ли уже перевода на этот язык
    if cluster.translations.filter(language=target_language).exists():
        messages.warning(request, f"⚠️ Перевод на {target_language.name} уже существует")
        return redirect("article:article_editor", pk=cluster_id)

    # Получаем основной перевод (русский или первый доступный)
    source_translation = cluster.translations.filter(language__code="ru").first()
    if not source_translation:
        source_translation = cluster.translations.first()

    if not source_translation:
        messages.error(request, "⚠️ Нет исходного текста для перевода")
        return redirect("article:article_editor", pk=cluster_id)

    # Запускаем фоновую задачу перевода
    task_id = str(uuid.uuid4())

    # Инициализируем прогресс
    cache.set(
        f"progress_{task_id}",
        {
            "percent": 0,
            "message": "Подготовка к переводу...",
            "status": "running",
            "logs": ["🚀 Запуск перевода..."],
            "task_id": task_id,
        },
        timeout=3600,
    )

    def run_translation():
        try:
            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 20,
                    "message": f"🤖 AI переводит на {target_language.name}...",
                    "status": "running",
                    "logs": ["🤖 Отправка текста в AI..."],
                    "task_id": task_id,
                },
                timeout=3600,
            )

            # Получаем промпт для перевода
            from prompts.services import get_system_instruction

            context = {
                "target_lang": target_language.name,
                "original_title": source_translation.title,
                "article_content": source_translation.content,
            }

            trans_prompt = get_system_instruction("translation_strict", context)

            # Генерируем перевод
            provider = "openai"  # Или возьми из настроек
            trans_raw = generate_text(provider, trans_prompt, max_tokens=2500)
            trans_data = parse_ai_json(trans_raw)

            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 80,
                    "message": "💾 Сохранение перевода...",
                    "status": "running",
                    "logs": ["💾 Сохранение в базу..."],
                    "task_id": task_id,
                },
                timeout=3600,
            )

            # Создаём перевод
            ArticleTranslation.objects.create(
                cluster=cluster,
                language=target_language,
                title=trans_data.get("title", source_translation.title),
                content=trans_data.get("content", source_translation.content),
                description=trans_data.get("description", ""),
                hashtags=trans_data.get("hashtags", ""),
                status="draft",
            )

            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 100,
                    "message": "✅ Перевод создан!",
                    "status": "done",
                    "logs": ["✅ Перевод успешно создан!"],
                    "task_id": task_id,
                    "redirect_url": f"/article/editor/{cluster.id}/",
                },
                timeout=3600,
            )

        except Exception as e:
            print(f"❌ Ошибка перевода: {e}")
            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 0,
                    "message": f"❌ Ошибка: {str(e)}",
                    "status": "error",
                    "logs": [f"❌ Ошибка: {str(e)}"],
                    "task_id": task_id,
                },
                timeout=3600,
            )
        finally:
            from django.db import connection

            connection.close()

    # Запускаем поток
    threading.Thread(target=run_translation, daemon=True).start()

    # Возвращаем JSON для AJAX
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "status": "ok",
                "task_id": task_id,
                "stream_url": f"/article/generation-stream/?task_id={task_id}",
            }
        )

    messages.success(request, "🚀 Перевод запущен в фоне")
    return redirect("article:article_editor", pk=cluster_id)


# Новая логика написания статьи с моделью gpt-4o-mini
def script_dashboard(request):
    """Список текстов для роликов."""
    # Обработка POST (удаление/смена статуса)
    if request.method == "POST":
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_scripts")

        if selected_ids:
            scripts = VideoScript.objects.filter(id__in=selected_ids)

            if action == "delete_selected":
                count, _ = scripts.delete()
                messages.success(request, f"✅ Удалено {count} текстов.")
            elif action == "change_status":
                new_status = request.POST.get("new_status")
                if new_status:
                    scripts.update(status=new_status)
                    messages.success(request, f"✅ Статус изменён для {scripts.count()} текстов.")
        else:
            messages.warning(request, "⚠️ Ничего не выбрано.")

        return redirect("article:video_script_list")

    # Статистика
    scripts_qs = VideoScript.objects.all()
    stats = {
        "total": scripts_qs.count(),
        "draft": scripts_qs.filter(status="draft").count(),
        "approved": scripts_qs.filter(status="approved").count(),
        "rejected": scripts_qs.filter(status="rejected").count(),
    }

    # Список
    scripts = scripts_qs.select_related("research_project").order_by("-created_at")

    context = {
        "scripts": scripts,
        "total": stats["total"],
        "stats": stats,
    }
    return render(request, "article/script_dashboard.html", context)


def script_generate(request):
    """Генерация вирусного текста для ролика."""
    if request.method == "POST":
        form = VideoScriptForm(request.POST)

        if form.is_valid():
            research_project = form.cleaned_data["research_project"]
            provider_name = form.cleaned_data["ai_provider"]
            prompt_code = form.cleaned_data["script_prompt"]
            focus_notes = form.cleaned_data.get("focus_notes", "")

            # Создаём черновик VideoScript
            script = VideoScript.objects.create(
                research_project=research_project,
                title=f"Текст: {research_project.topic}",
                provider=provider_name,
                status="draft",
            )

            task_id = str(uuid.uuid4())
            redirect_url = f"/article/api/generation_stream/{script.pk}/"

            # Инициализируем прогресс-бар
            pb = ProgressManager(task_id=task_id, redirect_url=redirect_url, timeout=CACHE_TIMEOUT)
            pb.init("🚀 Запуск генерации текста...", log_msg=f"Тема: {research_project.topic}")

            # Фоновая задача
            def run_generation():
                try:
                    pb.update(20, "🤖 Анализ исследования...", log_msg="Извлечение фактов")

                    # TODO: Здесь будет вызов сервиса generate_video_script
                    # Пока просто имитация для теста
                    import time

                    time.sleep(3)

                    pb.update(60, "✅ Текст сгенерирован", log_msg="Валидация структуры")

                    # TODO: Сохранение реальных данных
                    # script.script_data = script_data
                    # script.status = "approved"
                    # script.save()

                    pb.update(90, "💾 Сохранение в базу...", log_msg="Готово")
                    pb.done(100, "✅ Текст успешно создан!", log_msg="Перенаправление...")

                except Exception as exc:
                    print(f"❌ Ошибка генерации текста {task_id}: {exc}")
                    script.status = "rejected"
                    script.save()
                    pb.fail(str(exc))
                finally:
                    from django.db import connection

                    connection.close()

            # Запуск потока
            threading.Thread(target=run_generation, daemon=True).start()

            # Ответ для AJAX (модалка прогресса)
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.content_type == "application/json"
            ):
                return JsonResponse(
                    {
                        "status": "ok",
                        "task_id": task_id,
                        "stream_url": f"/article/api/generation_stream/?task_id={task_id}",
                    }
                )

            messages.success(request, "Генерация текста запущена.")
            return redirect("article:script_dashboard")

        else:
            if request.content_type == "application/json":
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
            messages.error(request, "Ошибка в форме.")

    else:
        form = VideoScriptForm()

    context = {
        "form": form,
    }
    return render(request, "article/script_generate.html", context)


def script_detail(request, pk):
    """Детальная страница текста для ролика."""
    script = get_object_or_404(
        VideoScript.objects.select_related("research_project", "cluster"), pk=pk
    )

    # Обработка POST (редактирование) — пока заглушка
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_status":
            new_status = request.POST.get("status")
            if new_status in ["draft", "approved", "rejected"]:
                script.status = new_status
                script.save()
                messages.success(request, f"✅ Статус изменён на '{script.get_status_display()}'")
            else:
                messages.error(request, "⚠️ Неверный статус")

        return redirect("article:script_detail", pk=script.pk)

    context = {
        "script": script,
    }
    return render(request, "article/script_detail.html", context)
