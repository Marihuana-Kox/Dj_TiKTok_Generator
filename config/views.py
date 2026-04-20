from django.shortcuts import render, redirect
from django.contrib import messages
from .models import SystemConfig


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
