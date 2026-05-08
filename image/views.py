# image/views.py
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from article.models import ArticleCluster
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from ai_inspector.models import AIProvider
from .models import ImagePrompt, ImageProject
from .services import generate_storyboard, generate_image_from_prompt
import uuid
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
    # Базовый контекст
    context = {
        'page_title': 'Новый проект',
        'articles': [],
        'show_modal': False,
        'project_data': None,
    }

    # 1. Получаем провайдеров
    providers_qs = AIProvider.objects.filter(is_active=True).order_by('name')
    context['providers'] = providers_qs

    # 2. Подготавливаем статьи
    articles_qs = ArticleCluster.objects.all().order_by('-created_at')[:50]
    articles_list = []
    for art in articles_qs:
        ru_trans = art.translations.filter(language__code='ru').first()
        if ru_trans:
            title = ru_trans.title
        elif art.translations.exists():
            first_trans = art.translations.first()
            title = f"{first_trans.title} ({first_trans.language.code.upper()})"
        else:
            title = "Без названия"
        articles_list.append({'id': art.id, 'title': title})

    context['articles'] = articles_list

    if request.method == 'POST':
        # Проверяем, это AJAX или обычная форма
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return _handle_ajax_create(request)

        # Обычная форма (оставляем как запасной вариант)
        return _handle_form_create(request)

    return render(request, 'image/project_create.html', context)


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
    Страница редактирования промптов + генерация изображений с прогрессом.
    """

    project = get_object_or_404(ImageProject, id=pk)
    prompts = project.prompts.all().order_by('order')

    # Получаем image-провайдеров
    image_providers = AIProvider.objects.filter(
        is_active=True,
        provider_type='image'
    )

    # AJAX: Запрос прогресса генерации (Polling)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':

        # GET-запрос → проверяем прогресс
        if request.method == 'GET':
            task_id = request.GET.get('task_id')
            if not task_id:
                return JsonResponse({'error': 'No task_id'}, status=400)

            progress = cache.get(f'gen_progress_{task_id}')
            if progress:
                return JsonResponse(progress)
            else:
                # Если прогресса нет в кэше — считаем завершённым
                return JsonResponse({
                    'completed': True,
                    'completed_count': 0,
                    'total_count': 0,
                    'prompts_status': []
                })

        # POST-запрос → запускаем генерацию
        if request.method == 'POST':
            provider_name = request.POST.get('provider')
            selected_ids = request.POST.get('selected_prompts', '')
            aspect_ratio = request.POST.get(
                'aspect_ratio', project.aspect_ratio)
            style_preset = request.POST.get('style_preset', 'current')

            # Проверка провайдера
            if not provider_name:
                return JsonResponse({'success': False, 'error': 'Выберите провайдера'}, status=400)

            # Парсим ID выбранных промптов
            try:
                selected_ids = [int(x)
                                for x in selected_ids.split(',') if x.isdigit()]
            except (ValueError, AttributeError):
                return JsonResponse({'success': False, 'error': 'Неверный формат ID'}, status=400)

            selected_prompts = prompts.filter(id__in=selected_ids)

            if not selected_prompts.exists():
                return JsonResponse({'success': False, 'error': 'Выберите хотя бы один промпт'}, status=400)

            # Создаём task_id для отслеживания прогресса
            task_id = str(uuid.uuid4())

            # Инициализируем прогресс в кэше (таймаут 10 минут)
            cache.set(f'gen_progress_{task_id}', {
                'completed': False,
                'completed_count': 0,
                'total_count': selected_prompts.count(),
                'prompts_status': [{'id': p.id, 'status': 'pending'} for p in selected_prompts],
                'error': None
            }, timeout=600)

            # Запускаем генерацию
            try:
                with transaction.atomic():
                    for i, prompt in enumerate(selected_prompts):
                        # Пропускаем уже успешные
                        if prompt.generation_status == 'success':
                            # Обновляем статус в кэше
                            progress = cache.get(f'gen_progress_{task_id}')
                            if progress:
                                progress['prompts_status'][i]['status'] = 'success'
                                progress['completed_count'] = i + 1
                                cache.set(
                                    f'gen_progress_{task_id}', progress, timeout=600)
                            continue

                        # Статус: генерация
                        progress = cache.get(f'gen_progress_{task_id}')
                        if progress:
                            progress['prompts_status'][i]['status'] = 'generating'
                            cache.set(
                                f'gen_progress_{task_id}', progress, timeout=600)

                        # Генерируем изображение
                        generate_image_from_prompt(
                            prompt,
                            provider_name,
                            aspect_ratio=aspect_ratio,
                            style_preset=style_preset
                        )

                        # Статус: успех
                        progress = cache.get(f'gen_progress_{task_id}')
                        if progress:
                            progress['prompts_status'][i]['status'] = 'success'
                            progress['completed_count'] = i + 1
                            cache.set(
                                f'gen_progress_{task_id}', progress, timeout=600)

                # Завершено успешно
                progress = cache.get(f'gen_progress_{task_id}')
                if progress:
                    progress['completed'] = True
                    cache.set(f'gen_progress_{task_id}', progress, timeout=600)

                return JsonResponse({
                    'success': True,
                    'task_id': task_id,
                    'message': f'Сгенерировано {selected_prompts.count()} изображений'
                })

            except Exception as e:
                # Ошибка генерации
                progress = cache.get(f'gen_progress_{task_id}')
                if progress:
                    progress['completed'] = True
                    progress['error'] = str(e)
                    cache.set(f'gen_progress_{task_id}', progress, timeout=600)

                return JsonResponse({
                    'success': False,
                    'error': str(e),
                    'task_id': task_id
                }, status=500)

    # ОБЫЧНАЯ ФОРМА: Сохранение промптов
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save':
            for prompt in prompts:
                new_desc = request.POST.get(f'desc_{prompt.id}')
                new_prompt_text = request.POST.get(f'prompt_{prompt.id}')
                if new_desc:
                    prompt.scene_description = new_desc
                if new_prompt_text:
                    prompt.prompt_text = new_prompt_text
                prompt.save()
            messages.success(request, "✅ Промпты сохранены!")
            return redirect('image:project_edit', pk=project.id)

    # GET: Отображение страницы
    context = {
        'project': project,
        'prompts': prompts,
        'image_providers': image_providers,
    }
    return render(request, 'image/project_edit.html', context)


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
    """API для получения прогресса генерации"""
    from django.core.cache import cache

    # Получаем прогресс из cache
    progress = cache.get(f'generation_progress_{task_id}')

    if not progress:
        return JsonResponse({
            'completed': True,
            'completed_count': 0,
            'total_count': 0,
            'prompts_status': []
        })

    return JsonResponse(progress)
