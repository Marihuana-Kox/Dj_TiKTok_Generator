import json
import threading
from time import timezone
import time
from ai_inspector.services import generate_text
from prompts.services import render_article_prompt, render_structure_prompt
from .forms import ArticleGenerationForm
from .models import Article
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from generator.models import VideoProject, ScriptData
from django.http import JsonResponse, StreamingHttpResponse
ARTICLE_GEN_PROGRESS = {}


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


def article_dashboard(request):
    # Обработка удаления
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_selected':
            selected_ids = request.POST.getlist('selected_articles')
            if selected_ids:
                count, _ = Article.objects.filter(id__in=selected_ids).delete()
                messages.success(request, f"✅ Удалено {count} статей.")
            else:
                messages.warning(request, "⚠️ Вы не выбрали ни одной статьи.")
            return redirect('article:dashboard')

    articles = Article.objects.all().order_by('-updated_at')

    stats = {
        'total': articles.count(),
        'draft': articles.filter(status='draft').count(),
        'published': articles.filter(status='published').count(),
    }

    return render(request, 'article/dashboard.html', {'articles': articles, 'stats': stats})


def article_edit(request, pk):
    article = get_object_or_404(Article, pk=pk)

    if request.method == 'POST':
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Статья сохранена!")
            return redirect('article:dashboard')
    else:
        form = ArticleForm(instance=article)

    return render(request, 'article/edit.html', {'form': form, 'article': article})


def generation_modal(request):
    form = ArticleGenerationForm()
    return render(request, 'article/generate_modal.html', {'form': form})


def start_generation(request):
    if request.method == 'POST':
        form = ArticleGenerationForm(request.POST)
        if form.is_valid():
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            selected_ids = form.cleaned_data['idea_selection']
            ARTICLE_GEN_PROGRESS[session_key] = {'current': 0, 'total': len(
                selected_ids), 'percent': 0, 'message': 'Подготовка...', 'status': 'starting'}

            def run_task():
                count_variants = int(form.cleaned_data.get(
                    'count_variants', 1))  # Получаем число
                # Общее количество статей
                total_tasks = len(selected_ids) * count_variants
                current_task = 0

                for idea_id in selected_ids:
                    idea = VideoProject.objects.get(id=idea_id)

                    # Генерируем N вариантов для одной идеи
                    for v in range(count_variants):
                        current_task += 1
                        percent = int((current_task / total_tasks) * 100)

                        ARTICLE_GEN_PROGRESS[session_key].update({
                            'current': current_task,
                            'percent': percent,
                            'message': f'Пишем вариант {v+1}/{count_variants} для: {idea.angle[:20]}...',
                            'status': 'running'
                        })

                        try:
                            # ... тут твой код генерации текста ...
                            # prompt_txt = ...
                            # content = generate_text(...)

                            # Сохраняем статью (добавь номер варианта в заголовок если нужно)
                            title_suffix = f" (Вариант {v+1})" if count_variants > 1 else ""
                            Article.objects.create(
                                title=idea.angle + title_suffix,
                                content=content,
                                status='draft'
                            )

                        except Exception as e:
                            # Обработка ошибки
                            pass

                # После цикла обновляем статус идеи
                idea.status = 'completed'
                idea.updated_at = timezone.now()
                idea.save()

                ARTICLE_GEN_PROGRESS[session_key].update(
                    {'status': 'done', 'percent': 100})

            threading.Thread(target=run_task).start()
            return JsonResponse({'status': 'started'})
    return JsonResponse({'status': 'error'})


def generation_stream(request):
    def event_stream():
        session_key = request.session.session_key
        if not session_key:
            return
        last = -1
        while True:
            data = ARTICLE_GEN_PROGRESS.get(session_key)
            if data and (data['percent'] != last or data['status'] in ['done', 'error']):
                yield f" {json.dumps(data)}\n\n"
                last = data['percent']
                if data['status'] in ['done', 'error']:
                    time.sleep(1)
                    break
            time.sleep(0.5)
        if session_key in ARTICLE_GEN_PROGRESS:
            del ARTICLE_GEN_PROGRESS[session_key]

    response = StreamingHttpResponse(
        event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response
