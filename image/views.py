# image/views.py
import json
import time
import uuid

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
from .models import ImagePrompt, ImageProject
from .services import generate_storyboard, generate_image_from_prompt
from django.core.cache import cache
from django.db import transaction


@login_required
def image_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_projects')

        if action == 'delete_selected' and selected_ids:
            ImageProject.objects.filter(id__in=selected_ids).delete()
            messages.success(
                request, f'✅ Удалено проектов: {len(selected_ids)}')
            return redirect('image:dashboard')

        elif action == 'regenerate_failed' and selected_ids:
            # Логика перегенерации
            pass

    # 1. Получаем все проекты
    projects_qs = ImageProject.objects.select_related(
        'article').order_by('-created_at')

    # 2. ПОИСК и ФИЛЬТРЫ
    query = request.GET.get('q')
    if query:
        if query.isdigit():
            page_obj = projects_qs.filter(
                Q(id=int(query)) | Q(search_title__icontains=query))
        else:
            page_obj = projects_qs.filter(search_title__icontains=query)

    status_filter = request.GET.get('status')
    if status_filter:
        page_obj = projects_qs.filter(status=status_filter)

    # 3. Статистика (по реальным статусам из БД)
    total = ImageProject.objects.count()
    processing = ImageProject.objects.filter(status='processing').count()
    completed = ImageProject.objects.filter(
        status__in=['prompts_ready', 'completed', 'images_ready']).count()

    # 4. ПАГИНАЦИЯ (10 проектов на страницу)
    paginator = Paginator(projects_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Подготавливаем данные для таблицы
    projects_list = []
    for counter, project in enumerate(page_obj, start=1):
        total_prompts = project.prompts.count()
        completed_count = project.prompts.filter(
            generation_status='success').count()
        progress_percent = round(
            (completed_count / total_prompts * 100)) if total_prompts > 0 else 0

        article_title = "⚠️ Статья удалена"
        if project.article:
            ru_trans = project.article.translations.filter(
                language__code='ru').first()
            article_title = ru_trans.title if ru_trans else "Без названия"

        # Обратный номер строки (вызываем start_index() как метод!)
        reverse_num = paginator.count - (page_obj.start_index() + counter - 2)

        projects_list.append({
            'instance': project,
            'id': project.id,
            'reverse_num': reverse_num,
            'article_title': article_title,
            'style_name': project.style_preset,
            'total_prompts': total_prompts,
            'completed_count': completed_count,
            'progress_percent': progress_percent,
            'status': project.status,
            'created_at': project.created_at,
        })

    context = {
        'projects': projects_list,
        'page_obj': page_obj,  # ← Для пагинации
        'paginator': paginator,  # ← Для счётчика страниц
        'stats': {
            'total': total,
            'processing': processing,
            'completed': completed,
        }
    }

    return render(request, 'image/dashboard.html', context)


@login_required
def project_create(request):
    providers = AIProvider.objects.filter(is_active=True)
    articles = ArticleCluster.objects.all().order_by('-created_at')[:50]

    if request.method == 'POST':
        article_id = request.POST.get('article_id')
        provider_name = request.POST.get('provider')
        scenes_count = int(request.POST.get('scenes_count', 10))

        if not article_id or not provider_name:
            return JsonResponse({'success': False, 'error': 'Заполните все поля'})

        task_id = str(uuid.uuid4())
        cluster = get_object_or_404(ArticleCluster, id=article_id)

        project = ImageProject.objects.create(
            article=cluster,
            title=f"Проект для {cluster.id}",
            style_preset=request.POST.get('style_preset', 'cinematic'),
            custom_style_prompt=request.POST.get('custom_style', ''),
            aspect_ratio=request.POST.get('aspect_ratio', '9:16'),
            status='processing'
        )

        # Инициализация
        cache.set(f"progress_{task_id}", {
            'percent': 1,
            'message': 'Инициализация проекта...',
            'status': 'running',
            'logs': ['🚀 Запуск генерации раскадровки...'],
            'task_id': task_id
        }, timeout=3600)
        # 3. Фоновая задача

        def run_image_task():
            def update_img_progress(percent, message, status='running', final=False):
                # Эта функция теперь используется только для Ошибок или Финала
                data = cache.get(f"progress_{task_id}", {})
                logs = data.get('logs', [])
                if message and (not logs or logs[-1] != message):
                    logs.append(message)
                payload = {
                    'percent': percent, 'message': message, 'status': status,
                    'logs': logs[-15:], 'task_id': task_id
                }
                if final:
                    payload['redirect_url'] = reverse(
                        'image:project_edit', kwargs={'pk': project.id})
                cache.set(f"progress_{task_id}", payload, timeout=3600)

            try:
                # Шаг 1: Только уведомляем о начале
                update_img_progress(
                    5, "🚀 Подготовка и отправка запроса в AI...")

                # Шаг 2: Вызываем сервис и ПЕРЕДАЕМ task_id
                # Теперь ВСЯ анимация прогресса будет идти ИЗНУТРИ этой функции
                generate_storyboard(
                    project=project,
                    scenes_count=scenes_count,
                    provider_override=provider_name,
                    task_id=task_id  # <--- Передаем ID для реального прогресса
                )

                # Шаг 3: Финализация (выполнится, когда сервис закончит цикл)
                update_img_progress(
                    100, "✅ Все сцены успешно созданы!", status='done', final=True)

            except Exception as e:
                print(f"Ошибка генерации: {e}")
                update_img_progress(0, f"Ошибка: {str(e)}", status='error')
            finally:
                connection.close()

        threading.Thread(target=run_image_task, daemon=True).start()

        return JsonResponse({
            'success': True,
            'task_id': task_id,
            'project_id': project.id
        })

    return render(request, 'image/project_create.html', {
        'providers': providers,
        'articles': articles,
        'page_title': 'Создать проект'
    })


def _handle_ajax_create(request):
    """Обработка AJAX-запроса на создание проекта"""
    import json
    from .services import generate_storyboard

    try:
        article_id = request.POST.get('article_id')
        provider_code = request.POST.get('provider')
        gen_mode = request.POST.get('gen_mode', 'auto')

        # Валидация
        if not provider_code:
            return _json_error("Необходимо выбрать AI провайдера!")
        if not article_id:
            return _json_error("Необходимо выбрать статью!")

        # Настройки
        if gen_mode == 'manual':
            style_preset = request.POST.get('style_preset', 'cinematic')
            aspect_ratio = request.POST.get('aspect_ratio', '16:9')
            try:
                scenes_count = int(request.POST.get('scenes_count', 10))
            except ValueError:
                scenes_count = 10
            custom_style = request.POST.get('custom_style', '')
        else:
            style_preset = 'cinematic'
            aspect_ratio = '9:16'
            scenes_count = 10
            custom_style = ''

        article = get_object_or_404(ArticleCluster, id=article_id)

        # Создаем проект
        project = ImageProject.objects.create(
            article=article,
            style_preset=style_preset,
            aspect_ratio=aspect_ratio,
            custom_style_prompt=custom_style,
            status='processing_prompts'
        )

        # Запускаем генерацию
        generated_count = generate_storyboard(
            project, scenes_count, provider_override=provider_code)

        # Успех
        return JsonResponse({
            'success': True,
            'project_id': project.id,
            'count': generated_count,
            'redirect_url': reverse('image:project_edit', kwargs={'pk': project.id})
        })

    except Exception as e:
        print(f"!!! AJAX ERROR: {e}")
        return _json_error(str(e))


def _json_error(message):
    """Вспомогательная функция для ошибок"""
    return JsonResponse({
        'success': False,
        'error': message
    }, status=400)


def _handle_form_create(request):
    """Обычная обработка формы (не AJAX)"""
    try:
        article_id = request.POST.get('article_id')
        provider_code = request.POST.get('provider')
        gen_mode = request.POST.get('gen_mode', 'auto')

        if not provider_code:
            messages.error(request, "Выберите провайдера!")
            return redirect('image:project_create')
        if not article_id:
            messages.error(request, "Выберите статью!")
            return redirect('image:project_create')

        if gen_mode == 'manual':
            style_preset = request.POST.get('style_preset', 'cinematic')
            aspect_ratio = request.POST.get('aspect_ratio', '16:9')
            try:
                scenes_count = int(request.POST.get('scenes_count', 10))
            except ValueError:
                scenes_count = 10
            custom_style = request.POST.get('custom_style', '')
        else:
            style_preset = 'cinematic'
            aspect_ratio = '9:16'
            scenes_count = 10
            custom_style = ''

        article = get_object_or_404(ArticleCluster, id=article_id)

        project = ImageProject.objects.create(
            article=article,
            style_preset=style_preset,
            aspect_ratio=aspect_ratio,
            custom_style_prompt=custom_style,
            status='processing_prompts'
        )

        generated_count = generate_storyboard(
            project, scenes_count, provider_override=provider_code)

        messages.success(request, f"✅ Проект создан! Сцен: {generated_count}")
        return redirect('image:project_edit', pk=project.id)

    except Exception as e:
        messages.error(request, f"❌ Ошибка: {str(e)}")
        return redirect('image:project_create')


@login_required
def project_edit(request, pk):
    """
    Страница редактирования промптов + генерация изображений с фоновым прогрессом.
    """
    project = get_object_or_404(ImageProject, id=pk)
    prompts = project.prompts.all().order_by('order')
    image_providers = AIProvider.objects.filter(
        is_active=True, provider_type='image')

    # AJAX: Обработка генерации или проверки статуса
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':

        # 1. Проверка прогресса (GET)
        if request.method == 'GET':
            task_id = request.GET.get('task_id')
            # Мы проверяем и gen_progress_ (старый ключ) и progress_ (новый ключ для стрима) для совместимости
            progress = cache.get(f"progress_{task_id}") or cache.get(
                f"gen_progress_{task_id}")
            if progress:
                return JsonResponse(progress)
            return JsonResponse({'completed': True, 'percent': 100})

        # 2. Запуск генерации (POST)
        if request.method == 'POST':
            provider_name = request.POST.get('provider')
            selected_ids_str = request.POST.get('selected_prompts', '')
            aspect_ratio = request.POST.get(
                'aspect_ratio', project.aspect_ratio)
            style_preset = request.POST.get('style_preset', 'current')

            if not provider_name or not selected_ids_str:
                return JsonResponse({'success': False, 'error': 'Не выбраны промпты или провайдер'}, status=400)

            try:
                selected_ids = [
                    int(x) for x in selected_ids_str.split(',') if x.isdigit()]
                # Превращаем в список для итерации в потоке
                selected_prompts = list(prompts.filter(id__in=selected_ids))
            except:
                return JsonResponse({'success': False, 'error': 'Ошибка валидации ID'}, status=400)

            task_id = str(uuid.uuid4())

            # Инициализируем прогресс в кэше
            cache.set(f"progress_{task_id}", {
                'percent': 1,
                'message': f'Подготовка очереди из {len(selected_prompts)} кадров...',
                'status': 'running',
                'logs': ['🚀 Запуск процесса генерации...'],
                'task_id': task_id,
                'total_count': len(selected_prompts),
                'completed_count': 0
            }, timeout=3600)

            # ФОНОВАЯ ЗАДАЧА
            def run_generation_task():
                try:
                    total = len(selected_prompts)
                    for i, prompt in enumerate(selected_prompts):
                        current_num = i + 1

                        # Обновляем статус в логах
                        data = cache.get(f"progress_{task_id}", {})
                        data['percent'] = int((i / total) * 100)
                        data['message'] = f"Обработка кадра {current_num} из {total}"
                        data['completed_count'] = i
                        cache.set(f"progress_{task_id}", data, timeout=3600)

                        # Сама генерация (вызываем твой сервис)
                        generate_image_from_prompt(
                            prompt,
                            provider_name,
                            aspect_ratio=aspect_ratio,
                            style_preset=style_preset,
                            task_id=task_id,  # Передаем для детальных логов внутри сервиса
                            step_info=f"[{current_num}/{total}]"
                        )

                    # Финализация
                    cache.set(f"progress_{task_id}", {
                        'percent': 100,
                        'message': '✅ Все изображения успешно сгенерированы!',
                        'status': 'done',
                        'task_id': task_id,
                        'completed': True
                    }, timeout=3600)

                except Exception as e:
                    cache.set(f"progress_{task_id}", {
                        'status': 'error',
                        'message': f"Ошибка: {str(e)}",
                        'percent': 0
                    }, timeout=3600)
                finally:
                    connection.close()

            threading.Thread(target=run_generation_task, daemon=True).start()
            return JsonResponse({'success': True, 'task_id': task_id})

    # ОБЫЧНАЯ ФОРМА: Сохранение текста (кнопка "Сохранить")
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save':
            for prompt in prompts:
                prompt.scene_description = request.POST.get(
                    f'desc_{prompt.id}', prompt.scene_description)
                prompt.prompt_text = request.POST.get(
                    f'prompt_{prompt.id}', prompt.prompt_text)
                prompt.save()
            messages.success(request, "✅ Промпты сохранены!")
            return redirect('image:project_edit', pk=project.id)

    # GET: Отображение страницы
    return render(request, 'image/project_edit.html', {
        'project': project,
        'prompts': prompts,
        'image_providers': image_providers,
    })


@login_required
def project_settings(request, pk):
    project = get_object_or_404(ImageProject, id=pk)

    if request.method == 'POST':
        project.style_preset = request.POST.get('style_preset')
        project.custom_style_prompt = request.POST.get('custom_style')
        project.aspect_ratio = request.POST.get('aspect_ratio')

        if request.POST.get('action') == 'regenerate_prompts':
            project.reset_prompts()
            messages.success(
                request, "Настройки обновлены. Запуск перегенерации промптов...")
        else:
            messages.success(request, "Настройки сохранены.")

        project.save()
        return redirect('image:project_edit', pk=project.id)

    return render(request, 'image/project_settings.html', {'project': project})


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
        return JsonResponse({
            'completed': True,
            'percent': 100,
            'message': 'Завершено или не найдено',
            'status': 'done',
            'completed_count': 0,
            'total_count': 0
        })

    # Добавляем флаг завершения для JS, если статус 'done'
    if progress.get('status') == 'done':
        progress['completed'] = True

    return JsonResponse(progress)


def generation_stream(request):
    task_id = request.GET.get('task_id')

    def event_stream():
        while True:
            data = cache.get(f"progress_{task_id}")
            if data:
                yield f"data: {json.dumps(data)}\n\n"
                if data.get('status') in ['done', 'error']:
                    break
            time.sleep(1)
    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
