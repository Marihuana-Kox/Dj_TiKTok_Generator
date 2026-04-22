from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from generator.models import VideoProject, ScriptData


def article_editor(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)

    # Получаем или создаем объект сценария
    script, created = ScriptData.objects.get_or_create(project=project)

    if request.method == 'POST':
        action = request.POST.get('action')
        # --- ДЕЙСТВИЕ: ДОБАВЛЕНИЕ НОВОГО ЯЗЫКА ---
        if action == 'add_language':
            lang_code = request.POST.get('new_lang_code')
            new_text = request.POST.get('new_lang_text')

            if lang_code and new_text:
                # Маппинг кодов языков на имена полей в модели ScriptData
                # Если у тебя в модели нет полей script_es, script_fr и т.д.,
                # нам придется использовать JSONField или добавить поля динамически.
                # ДЛЯ ПРОСТОТЫ сейчас мы будем сохранять новые языки в metadata['translations']

                translations = script.metadata.get('translations', {})
                translations[lang_code] = new_text
                script.metadata['translations'] = translations
                script.save()

                messages.success(
                    request, f"✅ Перевод на {lang_code.upper()} добавлен!")
            else:
                messages.error(request, "❌ Заполните все поля!")

            return redirect('article:article_editor', pk=pk)

        if action in ['save_text_only', 'go_to_images']:
            # Сохраняем основные тексты
            script.script_full = request.POST.get('script_en')
            script.script_ru = request.POST.get('script_ru')
            script.script_de = request.POST.get('script_de', '')

            # Сохраняем Мета-данные
            script.title = request.POST.get('title', '')
            script.hashtags = request.POST.get('hashtags', '')

            # Сохраняем описание в metadata
            metadata = script.metadata or {}
            metadata['description'] = request.POST.get('description', '')
            script.metadata = metadata

            script.save()

            if action == 'save_text_only':
                messages.success(request, "✅ Все данные сохранены!")
                return redirect('article:article_editor', pk=pk)

            elif action == 'go_to_images':
                # Тут логика перехода к картинкам...
                return redirect('image:image_prompt_editor', pk=pk)

        # Сохраняем отредактированные промпты (они приходят как JSON строка или список, тут упростим до текста)
        # Для удобства сделаем отдельное поле или будем парсить из textarea.
        # Давайте добавим поле image_prompts_json в модель ScriptData?
        # Пока просто сохраним в metadata как список строк, разделенных новой строкой для простоты ввода

        # Одно большое поле с переносами строк
        prompts_text = request.POST.get('image_prompts_text')
        # Превращаем текст обратно в список
        prompts_list = [p.strip()
                        for p in prompts_text.split('\n') if p.strip()]
        script.metadata['image_prompts'] = prompts_list

        script.save()

        messages.success(request, "✅ Статья и промпты сохранены!")
        # Остаемся на той же странице, чтобы видеть изменения
        return redirect('article:article_editor', pk=pk)

    # Получаем промпты для отображения (из metadata или создаем пустые)
    initial_prompts = script.metadata.get('image_prompts', [])
    # Превращаем список в текст для textarea (каждый промпт с новой строки)
    prompts_text_display = "\n".join(
        initial_prompts) if initial_prompts else ""

    context = {
        'project': project,
        'script': script,
        'prompts_text': prompts_text_display,
        # Ссылка на следующий этап (пока заглушка)
        'next_step_url': '#'
    }
    return render(request, 'article/article_editor.html', context)
