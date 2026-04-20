from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import ArticleStructureTemplate, SystemConfig


def template_list(request):
    """Список всех шаблонов структур."""
    templates = ArticleStructureTemplate.objects.all()
    return render(request, 'config/template_list.html', {'templates': templates})


def template_edit(request, pk=None):
    """Создание или редактирование шаблона."""
    if pk:
        template = get_object_or_404(ArticleStructureTemplate, pk=pk)
        title = "Редактировать шаблон"
    else:
        template = None
        title = "Новый шаблон"

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        structure_prompt = request.POST.get('structure_prompt')
        is_active = request.POST.get('is_active') == 'on'

        if not name or not structure_prompt:
            messages.error(request, "Название и Промпт обязательны!")
        else:
            if template:
                template.name = name
                template.description = description
                template.structure_prompt = structure_prompt
                template.is_active = is_active
                template.save()
                messages.success(request, f"Шаблон '{name}' обновлен!")
            else:
                ArticleStructureTemplate.objects.create(
                    name=name,
                    description=description,
                    structure_prompt=structure_prompt,
                    is_active=is_active
                )
                messages.success(request, f"Шаблон '{name}' создан!")
            return redirect('config:template_list')

    context = {
        'template': template,
        'title': title
    }
    return render(request, 'config/template_form.html', context)


def template_delete(request, pk):
    """Удаление шаблона."""
    template = get_object_or_404(ArticleStructureTemplate, pk=pk)
    name = template.name
    template.delete()
    messages.success(request, f"Шаблон '{name}' удален.")
    return redirect('config:template_list')


def dashboard(request):
    # Получаем настройки (или создаем дефолтные)
    config = SystemConfig.get_config()

    if request.method == 'POST':
        # Обновляем поля из формы
        config.operation_mode = request.POST.get('operation_mode')

        config.openai_key = request.POST.get('openai_key')
        config.gemini_key = request.POST.get('gemini_key')
        config.hf_key = request.POST.get('hf_key')
        config.elevenlabs_key = request.POST.get('elevenlabs_key')

        config.default_article_model = request.POST.get(
            'default_article_model')
        config.default_image_model = request.POST.get('default_image_model')

        config.auto_translate_languages = request.POST.get(
            'auto_translate_languages')
        config.auto_generate_images = request.POST.get(
            'auto_generate_images') == 'on'
        config.auto_generate_voice = request.POST.get(
            'auto_generate_voice') == 'on'
        config.auto_assemble_video = request.POST.get(
            'auto_assemble_video') == 'on'

        config.save()
        messages.success(request, "✅ Настройки успешно сохранены!")
        return redirect('config:dashboard')

    context = {
        'config': config,
        # Передаем список языков для чекбоксов или мульти-выбора (опционально)
    }
    return render(request, 'config/dashboard.html', context)
