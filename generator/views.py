from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
import os
from .models import VideoProject, MediaAsset, ScriptData

# Импортируем логику из модулей-библиотек
from article.providers import GeminiProvider, OpenAIProvider, get_provider as get_article_provider
from config.models import SystemConfig, ArticleStructureTemplate


def project_list(request):
    projects = VideoProject.objects.all()
    return render(request, 'generator/project_list.html', {'projects': projects})


def project_detail(request, pk):
    """Страница просмотра проекта. Кнопка ведет на настройку генерации."""
    project = get_object_or_404(VideoProject, pk=pk)
    return render(request, 'generator/project_detail.html', {'project': project})


def generate_config(request, pk):
    """
    Страница настройки и запуска генерации статьи.
    """
    project = get_object_or_404(VideoProject, pk=pk)

    # Значения по умолчанию для формы
    default_system_prompt = (
        "You are a professional historical documentary scriptwriter for TikTok/Shorts. "
        "Your style is engaging, mysterious, and fact-based but dramatic."
    )

    if request.method == 'POST':
        # 1. Получаем данные из формы
        selected_provider_name = request.POST.get('provider')
        system_prompt_style = request.POST.get('system_prompt')
        languages = request.POST.getlist('languages')
        # Получаем ID выбранного шаблона
        template_id = request.POST.get('structure_template_id')
        structure_text = None

        if template_id:
            try:
                tpl = ArticleStructureTemplate.objects.get(id=template_id)
                structure_text = tpl.structure_prompt
            except ArticleStructureTemplate.DoesNotExist:
                pass

        topic = request.POST.get('topic', project.topic)
        angle = request.POST.get('angle', project.angle)
        notes = request.POST.get('notes', project.notes)

        try:
            project.status = 'processing'
            project.save()

            # 2. Загрузка настроек из БД
            config = SystemConfig.get_config()

            # Определение провайдера
            provider_name = selected_provider_name or config.default_article_model.split(
                '-')[0]
            api_key = None
            model_name = config.default_article_model

            if 'openai' in provider_name.lower():
                api_key = config.openai_key
                if not api_key:
                    raise ValueError("OpenAI Key не указан в настройках!")
                provider = OpenAIProvider(model=model_name, api_key=api_key)

            elif 'gemini' in provider_name.lower():
                api_key = config.gemini_key
                if not api_key:
                    raise ValueError("Gemini Key не указан в настройках!")
                provider = GeminiProvider(model=model_name, api_key=api_key)
            else:
                raise ValueError(f"Неизвестный провайдер: {provider_name}")

            # Применяем ключ HF для картинок (на будущее)
            if config.hf_key:
                os.environ['HF_API_TOKEN'] = config.hf_key

            # 3. Генерация статьи
            article_data = provider.generate(
                topic=topic,
                angle=angle,
                notes=notes,
                languages=languages,
                system_instruction=system_prompt_style,
                structure_template=structure_text
            )

            # 4. Сохранение в БД
            ScriptData.objects.update_or_create(
                project=project,
                defaults={
                    'script_full': article_data.script_en,
                    'script_ru': article_data.translations.get('ru', ''),
                    'script_de': article_data.translations.get('de', ''),
                    'title': article_data.title,
                    'hashtags': article_data.hashtags,
                    'metadata': {
                        'image_prompts': article_data.image_prompts,
                        'structure_plan': article_data.structure_plan}
                }
            )

            project.status = 'completed'  # Или 'article_ready'
            project.save()

            messages.success(
                request, "✅ Статья сгенерирована! Переходим к редактору.")

            # 🔥 ВАЖНО: Редирект на редактор
            return redirect('article:article_editor', pk=project.pk)

        except Exception as e:
            project.status = 'failed'
            project.save()
            messages.error(request, f"❌ Ошибка: {str(e)}")

            # Возвращаем форму с ошибкой (чтобы пользователь мог попробовать снова)
            context = {
                'project': project,
                'default_system_prompt': system_prompt_style or default_system_prompt,
                'providers': [
                    {'id': 'openai', 'name': 'OpenAI'},
                    {'id': 'gemini', 'name': 'Google Gemini'},
                ],
                'structure_templates': ArticleStructureTemplate.objects.filter(is_active=True),
            }
            return render(request, 'generator/generate_config.html', context)

    # 🔥 ВАЖНО: Обработка GET запроса (когда просто открываем страницу)
    # Этот блок должен быть ВНЕ блока if request.method == 'POST'
    context = {
        'project': project,
        'default_system_prompt': default_system_prompt,
        'providers': [
            {'id': 'openai', 'name': 'OpenAI (GPT-4o)'},
            {'id': 'gemini', 'name': 'Google Gemini 1.5'},
        ],
        'structure_templates': ArticleStructureTemplate.objects.filter(is_active=True),
    }
    return render(request, 'generator/generate_config.html', context)
