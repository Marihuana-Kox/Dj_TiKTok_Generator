from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from generator.models import VideoProject, ScriptData


def article_editor(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)

    # Получаем или создаем объект сценария
    script, created = ScriptData.objects.get_or_create(project=project)

    if request.method == 'POST':
        # Сохраняем все изменения из формы
        script.script_full = request.POST.get('script_en')
        script.script_ru = request.POST.get('script_ru')
        script.title = request.POST.get('title')
        script.hashtags = request.POST.get('hashtags')

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
