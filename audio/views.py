from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import AudioProject, AudioTrack
from article.models import Article
from ai_inspector.models import AIProvider


@login_required
def audio_dashboard(request):
    """Дашборд аудио проектов"""
    projects_qs = AudioProject.objects.filter(
        user=request.user).order_by('-created_at')

    # Пагинация
    paginator = Paginator(projects_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Подготовка данных для таблицы
    projects_list = []
    for idx, project in enumerate(page_obj):
        tracks_count = project.tracks.count()
        completed_count = project.tracks.filter(status='success').count()

        projects_list.append({
            'instance': project,
            'id': project.id,
            'title': project.title,
            'article_title': project.article.title if project.article else 'Без статьи',
            'provider': project.provider,
            'status': project.status,
            'tracks_count': tracks_count,
            'completed_count': completed_count,
            'created_at': project.created_at,
        })

    # Обработка массовых действий
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_projects')

        if action == 'delete_selected' and selected_ids:
            AudioProject.objects.filter(
                id__in=selected_ids, user=request.user).delete()
            messages.success(
                request, f'✅ Удалено проектов: {len(selected_ids)}')
            return redirect('audio:dashboard')

    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'projects_list': projects_list,
    }
    return render(request, 'audio/dashboard.html', context)


@login_required
def audio_create(request):
    """Создание аудио проекта"""
    if request.method == 'POST':
        article_id = request.POST.get('article_id')
        provider_name = request.POST.get('provider')

        if not article_id or not provider_name:
            return JsonResponse({'success': False, 'error': 'Выберите статью и провайдера'}, status=400)

        try:
            article = Article.objects.get(id=article_id)
            provider = AIProvider.objects.get(
                name=provider_name, is_active=True)

            # Создаём проект
            project = AudioProject.objects.create(
                user=request.user,
                article=article,
                title=f"Озвучка: {article.title[:50]}",
                provider=provider_name,
                language='ru'
            )

            # Разбиваем статью на треки (по абзацам)
            paragraphs = article.content.split(
                '\n\n') if article.content else []
            for i, text in enumerate(paragraphs[:10]):  # Максимум 10 треков
                if text.strip():
                    AudioTrack.objects.create(
                        project=project,
                        order=i + 1,
                        text=text.strip()[:500]  # Максимум 500 символов
                    )

            return JsonResponse({
                'success': True,
                'redirect_url': f'/audio/{project.id}/edit/'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # GET: форма создания
    articles = Article.objects.all()[:50]
    providers = AIProvider.objects.filter(
        is_active=True, provider_type='audio')

    context = {
        'articles': articles,
        'providers': providers,
    }
    return render(request, 'audio/audio_create.html', context)


@login_required
def audio_edit(request, pk):
    """Редактирование аудио проекта"""
    project = get_object_or_404(AudioProject, id=pk, user=request.user)
    tracks = project.tracks.all().order_by('order')

    # Получаем audio-провайдеров
    audio_providers = AIProvider.objects.filter(
        is_active=True, provider_type='audio')

    # AJAX: генерация аудио
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.method == 'POST':
            # Логика генерации (добавим позже)
            return JsonResponse({'success': True, 'message': 'Генерация запущена'})

    context = {
        'project': project,
        'tracks': tracks,
        'audio_providers': audio_providers,
    }
    return render(request, 'audio/audio_edit.html', context)
