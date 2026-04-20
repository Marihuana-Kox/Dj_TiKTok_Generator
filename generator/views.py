from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
import os
from .models import VideoProject, MediaAsset, ScriptData

# Импортируем логику из модулей-библиотек
from article.providers import get_provider as get_article_provider
from config.models import SystemConfig


def project_list(request):
    projects = VideoProject.objects.all()
    return render(request, 'generator/project_list.html', {'projects': projects})


def project_detail(request, pk):
    """Страница просмотра проекта. Кнопка ведет на настройку генерации."""
    project = get_object_or_404(VideoProject, pk=pk)
    return render(request, 'generator/project_detail.html', {'project': project})


def generate_config(request, pk):
    """
    Страница настройки и запуска генерации.
    """
    project = get_object_or_404(VideoProject, pk=pk)

    # Значения по умолчанию для формы (если в БД еще пусто)
    default_system_prompt = (
        "You are a professional historical documentary scriptwriter for TikTok/Shorts. "
        "Your style is engaging, mysterious, and fact-based but dramatic."
    )

    if request.method == 'POST':
        # 1. Получаем данные из формы (выбор пользователя)
        selected_provider_name = request.POST.get(
            'provider')  # 'openai' или 'gemini'
        system_prompt_style = request.POST.get('system_prompt')
        languages = request.POST.getlist('languages')  # ['ru', 'de']

        # Данные проекта (можно подправить перед запуском)
        topic = request.POST.get('topic', project.topic)
        angle = request.POST.get('angle', project.angle)
        notes = request.POST.get('notes', project.notes)

        try:
            project.status = 'processing'
            project.save()

            # =========================================================
            # 🚀 ШАГ ИНТЕГРАЦИИ НАСТРОЕК (НОВОЕ!)
            # =========================================================

            # А. Получаем глобальные настройки из БД
            config = SystemConfig.get_config()

            # Б. Определяем, какого провайдера используем.
            # Приоритет: Выбор в форме > Настройка по умолчанию в БД > Hardcode 'openai'
            provider_name = selected_provider_name or config.default_article_model.split(
                '-')[0]  # Грубое извлечение имени

            # В. Получаем API ключи из настроек БД
            api_key = None
            model_name = config.default_article_model

            if 'openai' in provider_name.lower():
                api_key = config.openai_key
                # Если пользователь выбрал конкретную модель в форме (можно добавить поле в форму), используем её, иначе из конфига
                if not api_key:
                    raise ValueError(
                        "OpenAI Key не указан в настройках системы!")

                # Инициализируем провайдера ЯВНО с ключом и моделью из БД
                provider = OpenAIProvider(model=model_name, api_key=api_key)

            elif 'gemini' in provider_name.lower():
                api_key = config.gemini_key
                if not api_key:
                    raise ValueError(
                        "Gemini Key не указан в настройках системы!")

                provider = GeminiProvider(model=model_name, api_key=api_key)

            else:
                # Фоллбэк на старую фабрику (если ключи в .env)
                provider = get_provider(provider_name)

            # Г. Применяем ключи для картинок (если они тоже берутся из конфига)
            if config.hf_key:
                os.environ['HF_API_TOKEN'] = config.hf_key
            # =========================================================

            # 2. Запускаем генерацию статьи через настроенный экземпляр
            article_data = provider.generate(
                topic=topic,
                angle=angle,
                notes=notes,
                languages=languages,
                system_instruction=system_prompt_style  # Передаем стиль из формы
            )

            # 3. Сохраняем текст в БД
            ScriptData.objects.update_or_create(
                project=project,
                defaults={
                    'script_full': article_data.script_en,
                    'script_ru': article_data.translations.get('ru', ''),
                    'script_de': article_data.translations.get('de', ''),
                    'title': article_data.title,
                    'hashtags': article_data.hashtags,
                }
            )

            # 4. Генерируем картинки (используем ключ из БД, который мы положили в os.environ выше)
            # Примечание: Твой image сервис должен уметь брать ключ из env или передай его явно, если доработаешь image модуль
            from image.fal_provider import generate_images_batch  # Убедись, что путь верный

            output_folder = os.path.join(
                settings.MEDIA_ROOT, 'projects', str(project.id))
            image_paths = generate_images_batch(
                prompts=article_data.image_prompts,
                output_folder=output_folder,
                topic=project.topic
            )

            # Сохраняем картинки в БД
            for i, path in enumerate(image_paths):
                rel_path = os.path.relpath(path, settings.MEDIA_ROOT)
                MediaAsset.objects.create(
                    project=project,
                    asset_type='image',
                    file=rel_path,
                    prompt_used=article_data.image_prompts[i],
                    order=i
                )

            project.status = 'completed'
            project.save()
            messages.success(
                request, f"✅ Успешно сгенерировано через {provider_name.upper()} ({model_name})!")
            return redirect('project_detail', pk=project.pk)

        except Exception as e:
            project.status = 'failed'
            project.save()
            messages.error(request, f"❌ Ошибка генерации: {str(e)}")
            # Возвращаем форму с ошибкой, чтобы пользователь мог исправить
            context = {
                'project': project,
                'default_system_prompt': system_prompt_style or default_system_prompt,
                'providers': [
                    {'id': 'openai', 'name': 'OpenAI'},
                    {'id': 'gemini', 'name': 'Google Gemini'},
                ]
            }
            return render(request, 'generator/generate_config.html', context)

    # GET запрос: просто показываем форму
    context = {
        'project': project,
        'default_system_prompt': default_system_prompt,
        'providers': [
            {'id': 'openai', 'name': 'OpenAI (GPT-4o)'},
            {'id': 'gemini', 'name': 'Google Gemini 1.5'},
        ]
    }
    return render(request, 'generator/generate_config.html', context)
