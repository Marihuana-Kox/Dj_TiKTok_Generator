# image/views.py
import json
from pathlib import Path
import re
import time
import uuid

from django import db


from django.db import connection
import threading
from django.db.models import Q
from django.http import JsonResponse, StreamingHttpResponse
from django.urls import reverse
from article.models import ArticleCluster
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from ai_inspector.models import AIProvider
from audio.models import AudioProject
from prompts.models import ImagePromptTemplate
from .models import ImagePrompt, ImageProject
from .services import (
    generate_storyboard,
    generate_image_from_prompt,
    get_or_create_project_dir,
    handle_manual_image_upload,
)
from django.core.cache import cache


def get_project_image_progress(project):
    """
    Универсальная функция расчета прогресса картинок для любого проекта.
    Возвращает словарь с количеством кадров, готовых файлов и процентом.
    """
    # Загружаем все промпты (кадры), привязанные к этому проекту
    # (Замени .prompts на имя related_name в твоей модели ImageProject, если оно отличается)
    prompts = project.prompts.all()
    total_count = prompts.count()

    # Считаем только успешные кадры, у которых физически записан файл картинки
    # Исключаем пустые строки и null значения из поля image
    success_count = prompts.exclude(image="").exclude(image__isnull=True).count()

    # Считаем чистый процент (с защитой от деления на ноль)
    percent = int((success_count / total_count) * 100) if total_count > 0 else 0

    return {
        "total_tracks": total_count,
        "success_tracks": success_count,
        "progress_percent": percent,
        "project_ready": total_count > 0 and (total_count == success_count),
    }


@login_required
def image_dashboard(request):
    if request.method == "POST":
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_projects")

        if action == "delete_selected" and selected_ids:
            ImageProject.objects.filter(id__in=selected_ids).delete()
            messages.success(request, f"✅ Удалено проектов: {len(selected_ids)}")
            return redirect("image:dashboard")

        elif action == "regenerate_failed" and selected_ids:
            # Логика перегенерации
            pass

    # 1. Получаем все проекты
    projects_qs = ImageProject.objects.select_related("article").order_by("-created_at")

    # 2. ПОИСК и ФИЛЬТРЫ
    query = request.GET.get("q")
    if query:
        if query.isdigit():
            page_obj = projects_qs.filter(Q(id=int(query)) | Q(search_title__icontains=query))
        else:
            page_obj = projects_qs.filter(search_title__icontains=query)

    status_filter = request.GET.get("status")
    if status_filter:
        page_obj = projects_qs.filter(status=status_filter)

    # 3. Статистика (по реальным статусам из БД)
    total = ImageProject.objects.count()
    processing = ImageProject.objects.filter(status="processing").count()
    completed = ImageProject.objects.filter(
        status__in=["prompts_ready", "completed", "images_ready"]
    ).count()

    # 4. ПАГИНАЦИЯ (10 проектов на страницу)
    paginator = Paginator(projects_qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 5. Подготавливаем данные для таблицы
    projects_list = []
    for counter, project in enumerate(page_obj, start=1):
        total_prompts = project.prompts.count()
        completed_count = project.prompts.filter(generation_status="success").count()
        progress_percent = (
            round((completed_count / total_prompts * 100)) if total_prompts > 0 else 0
        )

        article_title = "⚠️ Статья удалена"
        if project.article:
            ru_trans = project.article.translations.filter(language__code="ru").first()
            article_title = ru_trans.title if ru_trans else "Без названия"

        # Обратный номер строки (вызываем start_index() как метод!)
        reverse_num = paginator.count - (page_obj.start_index() + counter - 2)

        projects_list.append(
            {
                "instance": project,
                "id": project.id,
                "reverse_num": reverse_num,
                "article_title": article_title,
                "style_name": project.style_preset,
                "total_prompts": total_prompts,
                "completed_count": completed_count,
                "progress_percent": progress_percent,
                "status": project.status,
                "created_at": project.created_at,
            }
        )

    context = {
        "projects": projects_list,
        "page_obj": page_obj,  # ← Для пагинации
        "paginator": paginator,  # ← Для счётчика страниц
        "stats": {
            "total": total,
            "processing": processing,
            "completed": completed,
        },
    }

    return render(request, "image/dashboard.html", context)


@login_required
def project_create(request):
    providers = AIProvider.objects.filter(is_active=True)
    articles = ArticleCluster.objects.all().order_by("-created_at")[:50]
    scenes_prompt = ImagePromptTemplate.objects.filter(is_active=True)  # ← 1. Для шаблона

    if request.method == "POST":
        article_id = request.POST.get("article_id")
        provider_name = request.POST.get("provider")
        scenes_count = int(request.POST.get("scenes_count", 10))
        prompt_code = request.POST.get("prompt_template", "storyboard_generator")

        prompt_content = None
        try:
            prompt_obj = ImagePromptTemplate.objects.get(
                code_name__iexact=prompt_code, is_active=True
            )
            prompt_content = prompt_obj.template_content
        except ImagePromptTemplate.DoesNotExist:
            fallback = ImagePromptTemplate.objects.filter(is_active=True).first()
            prompt_content = fallback.template_content if fallback else None

        if not prompt_content:
            return JsonResponse({"success": False, "error": "В БД нет активных шаблонов промптов."})

        if not article_id or not provider_name:
            return JsonResponse({"success": False, "error": "Заполните все поля"})

        task_id = str(uuid.uuid4())
        cluster = get_object_or_404(ArticleCluster, id=article_id)
        # 1. Извлекаем все переводы и определяем главный язык для имени папки
        all_translations = cluster.translations.all()
        main_translation = (
            cluster.translations.filter(language__code="ru").first() or cluster.translations.first()
        )
        main_title = getattr(main_translation, "title", f"Статья {cluster.id}")

        # 2. Создаем физическую папку на сервере
        project_dir, folder_name = get_or_create_project_dir(main_title, cluster.id)

        # 3. Создаем проект в БД с нормальным человеческим названием статьи
        project = ImageProject.objects.create(
            article=cluster,
            title=main_title,  # Изменено с f"Проект для {cluster.id}" на название статьи
            style_preset=request.POST.get("style_preset", "cinematic"),
            custom_style_prompt=request.POST.get("custom_style", ""),
            aspect_ratio=request.POST.get("aspect_ratio", "9:16"),
            status="processing",
        )

        # 4. Генерируем метафайлы для каждого перевода, который есть в БД
        for trans in all_translations:
            lang_code = trans.language.code
            # Достаем ЧИСТЫЙ оригинальный заголовок из базы данных (с пробелами, без подчеркиваний!)
            original_lang_title = getattr(trans, "title", "") or main_title
            lang_metadata = {
                "project_id": project.id,
                "article_id": cluster.id,
                "working_title": original_lang_title,
                "description": getattr(trans, "description", ""),
                "content": getattr(trans, "content", "") or getattr(trans, "body", "") or "",
                "hashtags": getattr(trans, "hashtags", ""),
                "language": lang_code,
                "folder_name": folder_name,
            }

            metadata_file_path = project_dir / f"metadata_{lang_code}.json"
            with open(metadata_file_path, "w", encoding="utf-8") as f:
                json.dump(lang_metadata, f, ensure_ascii=False, indent=4)

        cache.set(
            f"progress_{task_id}",
            {
                "percent": 1,
                "message": "Инициализация проекта...",
                "status": "running",
                "logs": [
                    "🚀 Запуск генерации раскадровки...",
                    f"📁 Создана единая директория проекта: projects/{folder_name}",
                    f"📝 Инициализировано метафайлов для языков: {', '.join([t.language.code for t in all_translations])}",
                ],
                "task_id": task_id,
            },
            timeout=3600,
        )

        def run_image_task():
            def update_img_progress(percent, message, status="running", final=False):
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
                    payload["redirect_url"] = reverse(
                        "image:project_edit", kwargs={"pk": project.id}
                    )
                cache.set(f"progress_{task_id}", payload, timeout=3600)

            try:
                update_img_progress(5, "🚀 Подготовка и отправка запроса в AI...")

                # ДОБАВИТЬ СТРОКУ:
                source_text = (
                    getattr(main_translation, "content", "")
                    or getattr(main_translation, "body", "")
                    or ""
                )

                # ОСТАВИТЬ ПРОВЕРКУ:
                if not source_text.strip():
                    update_img_progress(
                        0, "❌ Текст статьи пуст в главном переводе.", status="error"
                    )
                    return

                # ← 3. ВЫЗОВ СЕРВИСА (исправлено имя параметра + добавлен текст)
                generate_storyboard(
                    project=project,
                    scenes_count=scenes_count,
                    provider_override=provider_name,
                    task_id=task_id,
                    prompt_template=prompt_content,  # ← БЫЛО scenes_prompt=
                    source_text=source_text,  # ← ОБЯЗАТЕЛЬНО
                )

                update_img_progress(100, "✅ Все сцены успешно созданы!", status="done", final=True)
            except Exception as e:
                print(f"Ошибка генерации: {e}")
                update_img_progress(0, f"Ошибка: {str(e)}", status="error")
            finally:
                connection.close()

        threading.Thread(target=run_image_task, daemon=True).start()

        return JsonResponse({"success": True, "task_id": task_id, "project_id": project.id})

    return render(
        request,
        "image/project_create.html",
        {
            "providers": providers,
            "articles": articles,
            "scenes_prompt": scenes_prompt,  # ← 1. ТЕПЕРЬ ПЕРЕДАЁТСЯ В ШАБЛОН
            "page_title": "Создать проект",
        },
    )


def _handle_ajax_create(request):
    """Обработка AJAX-запроса на создание проекта"""
    import json
    from .services import generate_storyboard

    try:
        article_id = request.POST.get("article_id")
        provider_code = request.POST.get("provider")
        gen_mode = request.POST.get("gen_mode", "auto")

        # Валидация
        if not provider_code:
            return _json_error("Необходимо выбрать AI провайдера!")
        if not article_id:
            return _json_error("Необходимо выбрать статью!")

        # Настройки
        if gen_mode == "manual":
            style_preset = request.POST.get("style_preset", "cinematic")
            aspect_ratio = request.POST.get("aspect_ratio", "16:9")
            try:
                scenes_count = int(request.POST.get("scenes_count", 10))
            except ValueError:
                scenes_count = 10
            custom_style = request.POST.get("custom_style", "")
        else:
            style_preset = "cinematic"
            aspect_ratio = "9:16"
            scenes_count = 10
            custom_style = ""

        article = get_object_or_404(ArticleCluster, id=article_id)

        # Создаем проект
        project = ImageProject.objects.create(
            article=article,
            style_preset=style_preset,
            aspect_ratio=aspect_ratio,
            custom_style_prompt=custom_style,
            status="processing_prompts",
        )

        # Запускаем генерацию
        generated_count = generate_storyboard(
            project, scenes_count, provider_override=provider_code
        )

        # Успех
        return JsonResponse(
            {
                "success": True,
                "project_id": project.id,
                "count": generated_count,
                "redirect_url": reverse("image:project_edit", kwargs={"pk": project.id}),
            }
        )

    except Exception as e:
        print(f"!!! AJAX ERROR: {e}")
        return _json_error(str(e))


def _json_error(message):
    """Вспомогательная функция для ошибок"""
    return JsonResponse({"success": False, "error": message}, status=400)


def _handle_form_create(request):
    """Обычная обработка формы (не AJAX)"""
    try:
        article_id = request.POST.get("article_id")
        provider_code = request.POST.get("provider")
        gen_mode = request.POST.get("gen_mode", "auto")

        if not provider_code:
            messages.error(request, "Выберите провайдера!")
            return redirect("image:project_create")
        if not article_id:
            messages.error(request, "Выберите статью!")
            return redirect("image:project_create")

        if gen_mode == "manual":
            style_preset = request.POST.get("style_preset", "cinematic")
            aspect_ratio = request.POST.get("aspect_ratio", "16:9")
            try:
                scenes_count = int(request.POST.get("scenes_count", 10))
            except ValueError:
                scenes_count = 10
            custom_style = request.POST.get("custom_style", "")
        else:
            style_preset = "cinematic"
            aspect_ratio = "9:16"
            scenes_count = 10
            custom_style = ""

        article = get_object_or_404(ArticleCluster, id=article_id)

        project = ImageProject.objects.create(
            article=article,
            style_preset=style_preset,
            aspect_ratio=aspect_ratio,
            custom_style_prompt=custom_style,
            status="processing_prompts",
        )

        generated_count = generate_storyboard(
            project, scenes_count, provider_override=provider_code
        )

        messages.success(request, f"✅ Проект создан! Сцен: {generated_count}")
        return redirect("image:project_edit", pk=project.id)

    except Exception as e:
        messages.error(request, f"❌ Ошибка: {str(e)}")
        return redirect("image:project_create")


@login_required
def project_edit(request, pk):
    """
    Страница редактирования промптов + генерация изображений с фоновым прогрессом.
    """
    project = get_object_or_404(ImageProject, id=pk)
    prompts = project.prompts.all().order_by("order")
    image_providers = AIProvider.objects.filter(is_active=True, provider_type="image")

    progress_data = get_project_image_progress(project)
    # AJAX: Обработка генерации или проверки статуса
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # 1. Проверка прогресса (GET)
        if request.method == "GET":
            task_id = request.GET.get("task_id")
            progress = cache.get(f"progress_{task_id}") or cache.get(f"gen_progress_{task_id}")
            if progress:
                return JsonResponse(progress)
            return JsonResponse({"completed": True, "percent": 100})

        # 2. Запуск генерации (POST)
        if request.method == "POST":
            action = request.POST.get("action")  # новая строка для определения действия
            if action == "autosave_single":
                p_id = request.POST.get("prompt_id")
                new_text = request.POST.get("prompt_text")
                try:
                    prompt_obj = ImagePrompt.objects.get(id=p_id)
                    prompt_obj.prompt_text = new_text
                    prompt_obj.save()
                    return JsonResponse({"success": True})
                except Exception as e:
                    return JsonResponse({"success": False, "error": str(e)}, status=400)
            elif action == "manual_upload":
                p_id = request.POST.get("prompt_id")
                uploaded_file = request.FILES.get("image_file")

                if not p_id:
                    return JsonResponse(
                        {"success": False, "error": "ID кадра не передан"}, status=400
                    )
                if not uploaded_file:
                    return JsonResponse({"success": False, "error": "Файл не выбран"}, status=400)

                # Просто отдаем ID и файл в сервис. Всё!
                return handle_manual_image_upload(p_id, uploaded_file)

            provider_name = request.POST.get("provider")
            selected_ids_str = request.POST.get("selected_prompts", "")
            aspect_ratio = request.POST.get("aspect_ratio", project.aspect_ratio)
            style_preset = request.POST.get("style_preset", "current")

            if not provider_name or not selected_ids_str:
                return JsonResponse(
                    {"success": False, "error": "Не выбраны промпты или провайдер"},
                    status=400,
                )

            try:
                selected_ids = [int(x) for x in selected_ids_str.split(",") if x.isdigit()]

                # Находим кадры из выбранных, у которых ЕЩЕ НЕТ картинок (пустые слоты)
                empty_prompts_qs = (
                    prompts.filter(id__in=selected_ids).filter(image__isnull=True)
                    | prompts.filter(id__in=selected_ids).filter(image="")
                ).distinct()

                # Если передан специальный флаг принудительной перезаписи от пользователя
                force_regenerate = request.POST.get("force_regenerate") == "true"

                if force_regenerate:
                    # Если пользователь согласился на перегенерацию, берем ВСЕ выбранные ID
                    selected_prompts = list(prompts.filter(id__in=selected_ids))
                else:
                    # Иначе отправляем на генерацию только пустые слоты
                    selected_prompts = list(empty_prompts_qs)

                # Если пустых слотов нет и принудительный флаг не пришел, отправляем фронтенду статус для вызова Confirm
                if not selected_prompts and not force_regenerate:
                    return JsonResponse(
                        {
                            "success": False,
                            "requires_confirmation": True,
                            "message": "Некоторые или все выбранные кадры уже имеют готовые изображения. Перегенерировать их?",
                        }
                    )

            except Exception as val_err:
                return JsonResponse(
                    {"success": False, "error": f"Ошибка валидации ID: {str(val_err)}"}, status=400
                )
            task_id = str(uuid.uuid4())

            # Инициализируем прогресс в кэше
            cache.set(
                f"progress_{task_id}",
                {
                    "percent": 1,
                    "message": f"Подготовка очереди из {len(selected_prompts)} кадров...",
                    "status": "running",
                    "logs": ["🚀 Запуск процесса генерации..."],
                    "task_id": task_id,
                    "total_count": len(selected_prompts),
                    "completed_count": 0,
                },
                timeout=3600,
            )

            # Переводим объекты в список ID, чтобы безопасно читать их внутри изолированного потока потока
            selected_prompt_ids = [p.id for p in selected_prompts]

            # ФОНОВАЯ ЗАДАЧА
            def run_generation_task(prompt_ids):
                # 🔥 ИМПОРТИРУЕМ МОДУЛЬ ДЛЯ СБРОСА СОЕДИНЕНИЙ БД
                db.close_old_connections()  # <-- ЗАКРЫВАЕМ СТАРЫЕ ХВОСТЫ ТУТ
                try:
                    total = len(prompt_ids)

                    # --- ИНИЦИАЛИЗАЦИЯ ПАПКИ ПРОЕКТА ---
                    project_dir, folder_name = get_or_create_project_dir(
                        project.title, project.article.id
                    )
                    # relative_subfolder = f"projects/{folder_name}"

                    for i, p_id in enumerate(prompt_ids):
                        current_num = i + 1

                        # Ещё раз принудительно чистим коннекты перед каждым кадром на всякий случай
                        db.close_old_connections()

                        # Теперь этот запрос выполнится на 100% успешно и без падения потока!
                        prompt = ImagePrompt.objects.get(id=p_id)

                        scene_index = prompt.order if prompt.order > 0 else current_num
                        filename_base = f"pic_{scene_index}"

                        # Обновляем статус в кэше
                        data = cache.get(f"progress_{task_id}", {})
                        if data:
                            data["percent"] = int((i / total) * 100)
                            data["message"] = (
                                f"Обработка кадра {current_num} из {total} ({filename_base})"
                            )
                            data["completed_count"] = i
                            cache.set(f"progress_{task_id}", data, timeout=3600)

                        # --- СОЗДАНИЕ МЕТАФАЙЛА ДЛЯ КАРТИНКИ ---
                        # Синхронизируем имена полей ("prompt") с нашей ручной загрузкой!
                        pic_metadata = {
                            "prompt": getattr(prompt, "prompt_text", "")
                            or getattr(prompt, "prompt", ""),
                            "filename": f"{filename_base}.jpeg",  # Будет обновлено сервисом, если запишется png
                            "order": scene_index,
                            "description": getattr(prompt, "scene_description", "") or "",
                            "aspect_ratio": aspect_ratio,
                            "provider": provider_name,
                            "is_manual": False,
                        }

                        pic_json_path = project_dir / f"{filename_base}.json"
                        with open(pic_json_path, "w", encoding="utf-8") as f:
                            json.dump(pic_metadata, f, ensure_ascii=False, indent=4)

                        # --- ВЫЗОВ СЕРВИСА ГЕНЕРАЦИИ КАРТИНКИ ---
                        generate_image_from_prompt(
                            prompt=prompt,
                            provider_name=provider_name,
                            aspect_ratio=aspect_ratio,
                            style_preset=style_preset,
                            task_id=task_id,
                            step_info=f"[{current_num}/{total}]",
                            custom_filename=filename_base,
                        )

                        if current_num < total:
                            time.sleep(15)

                    # Финализация
                    cache.set(
                        f"progress_{task_id}",
                        {
                            "percent": 100,
                            "message": "✅ Все изображения успешно сгенерированы!",
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
                            "message": f"Ошибка генерации кадров: {str(e)}",
                            "percent": 0,
                        },
                        timeout=3600,
                    )
                finally:
                    connection.close()

            # Запускаем поток, передавая список ID
            threading.Thread(
                target=run_generation_task, args=(selected_prompt_ids,), daemon=True
            ).start()
            return JsonResponse({"success": True, "task_id": task_id})

    # ОБЫЧНАЯ ФОРМА: Сохранение текста (кнопка "Сохранить")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save":
            for prompt in prompts:
                prompt.scene_description = request.POST.get(
                    f"desc_{prompt.id}", prompt.scene_description
                )
                prompt.prompt_text = request.POST.get(f"prompt_{prompt.id}", prompt.prompt_text)
                prompt.save()
            messages.success(request, "✅ Промпты сохранены!")
            return redirect("image:project_edit", pk=project.id)

    audio_project = None
    audio_project = AudioProject.objects.filter(title__icontains=project.title.strip()).first()
    # GET: Отображение страницы
    return render(
        request,
        "image/project_edit.html",
        {
            "project": project,
            "prompts": prompts,
            "image_providers": image_providers,
            "audio_project": audio_project.pk if audio_project else None,
            # 🔥 Новые переменные для твоей простой шкалы прогресса в HTML
            "total_tracks": progress_data["total_tracks"],
            "success_tracks": progress_data["success_tracks"],
            "progress_percent": progress_data["progress_percent"],
            "project_ready": progress_data["project_ready"],
        },
    )


@login_required
def project_settings(request, pk):
    project = get_object_or_404(ImageProject, id=pk)

    if request.method == "POST":
        project.style_preset = request.POST.get("style_preset")
        project.custom_style_prompt = request.POST.get("custom_style")
        project.aspect_ratio = request.POST.get("aspect_ratio")

        if request.POST.get("action") == "regenerate_prompts":
            project.reset_prompts()
            messages.success(request, "Настройки обновлены. Запуск перегенерации промптов...")
        else:
            messages.success(request, "Настройки сохранены.")

        project.save()
        return redirect("image:project_edit", pk=project.id)

    return render(request, "image/project_settings.html", {"project": project})


@login_required
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


def generation_stream(request):
    task_id = request.GET.get("task_id")

    def event_stream():
        while True:
            data = cache.get(f"progress_{task_id}")
            # 🔥 ВСТАВЬ ЭТОТ ПРИНТ СЮДА:
            print("--- ЧТО ЛЕЖИТ В КЭШЕ СТРИМА ---:", data)
            if not data:
                yield f"data: {json.dumps({'percent': 0, 'message': 'Ожидание задачи...', 'status': 'processing'})}\n\n"
                time.sleep(1)
                continue
            # Явно формируем payload для модалки
            payload = {
                "percent": data.get("percent", 0),
                "message": data.get("message", ""),
                "status": data.get("status", "processing"),
                "redirect_url": data.get("redirect_url"),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if data.get("status") in ("done", "error"):
                break
            time.sleep(0.8)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
