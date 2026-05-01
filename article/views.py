import json
import re
import time
import threading
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib import messages

# Импорт моделей
from prompts.models import ArticlePrompt, SystemInstruction
from topics.models import VideoProject
from article.models import Article, ArticleCluster, ArticleTranslation, ImagePrompt, Language, SceneType
from article.forms import ArticleGenerationForm

# Импорт сервисов
from ai_inspector.services import generate_text
from prompts.services import get_system_instruction, render_article_prompt, render_system_instruction

# Глобальное хранилище прогресса
ARTICLE_GEN_PROGRESS = {}


def article_generate_page(request):
    form = ArticleGenerationForm()
    return render(request, 'article/generate.html', {'form': form})


def start_generation_api(request):
    """API endpoint для запуска генерации через AJAX"""
    if request.method == 'POST':
        form = ArticleGenerationForm(request.POST)
        if not form.is_valid():
            print(form.errors)  # Вывод ошибок в консоль
            return JsonResponse({'status': 'error', 'message': 'Invalid form data'})
        if form.is_valid():
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            selected_ids = form.cleaned_data['idea_selection']
            selected_lang_codes = form.cleaned_data['languages']

            # Гарантируем, что EN всегда есть
            if 'en' not in selected_lang_codes:
                selected_lang_codes.append('en')

            # Получаем выбранный Промпт
            prompt_code = form.cleaned_data['article_prompt']

            # Настройки картинок
            img_mode = form.cleaned_data['image_mode']
            manual_count = form.cleaned_data.get('manual_scene_count', 5)
            aspect_ratio = form.cleaned_data['aspect_ratio']
            art_style = form.cleaned_data['art_style']
            provider = form.cleaned_data['ai_provider']

            # Проверка: включена ли генерация промптов?
            generate_prompts = 'enable_prompts_toggle' in request.POST

            # Оценка шагов
            steps_per_idea = 1 + 1 + len(selected_lang_codes)
            if generate_prompts:
                steps_per_idea += 2

            total_steps_estimate = len(selected_ids) * steps_per_idea

            ARTICLE_GEN_PROGRESS[session_key] = {
                'current': 0,
                'total': total_steps_estimate,
                'percent': 0,
                'message': 'Инициализация...',
                'status': 'starting',
                'log': []
            }

            def run_task():
                current_step = 0

                try:
                    for idea_id in selected_ids:
                        print(
                            f"\n>>> [THREAD] Начало обработки идеи ID: {idea_id}")
                        update_progress(session_key, current_step,
                                        f"Загрузка идеи {idea_id}...")

                        try:
                            idea = VideoProject.objects.get(id=idea_id)
                        except VideoProject.DoesNotExist:
                            raise ValueError(f"Idea ID {idea_id} not found!")

                        # 1. Кластер
                        cluster = ArticleCluster.objects.create(
                            source_idea=idea)
                        current_step += 1
                        update_progress(session_key, current_step,
                                        f"Кластер создан: {idea.angle[:30]}")

                        # --- ПОДГОТОВКА ТЕМЫ И КОНТЕКСТА (ДВУЯЗЫЧНАЯ ЛОГИКА) ---
                        raw_topic = idea.angle
                        ai_topic_en = raw_topic
                        additional_context = ""

                        # Извлекаем данные из notes
                        if idea.notes and "AI_TOPIC_EN:" in idea.notes:
                            lines = idea.notes.split('\n')
                            # Первая строка - тема
                            ai_topic_en = lines[0].replace(
                                "AI_TOPIC_EN:", "").strip()
                            # Остальные строки - контекст (факты, вопросы)
                            additional_context = "\n".join(lines[1:]).strip()

                        print(f">>> [DEBUG] Тема для AI (EN): {ai_topic_en}")
                        print(additional_context)
                        print(
                            f">>> [DEBUG] Контекст (факты): {additional_context[:100]}...")

                        # --- ПРОМПТ СТАТЬИ (ИСПРАВЛЕНО: template_content + .render()) ---

                        selected_prompt_obj = None
                        prompt_name = ""

                        if prompt_code == 'random':
                            selected_prompt_obj = ArticlePrompt.objects.filter(
                                is_active=True).order_by('?').first()
                            prompt_name = f"Случайный ({selected_prompt_obj.code_name if selected_prompt_obj else 'None'})"
                        else:
                            selected_prompt_obj = ArticlePrompt.objects.filter(
                                code_name=prompt_code, is_active=True).first()
                            prompt_name = prompt_code

                        if selected_prompt_obj:
                            print(
                                f"✅ [DEBUG] НАЙДЕН ПРОМПТ: {selected_prompt_obj.code_name}")

                            # Используем встроенный метод .render() из базового класса BasePrompt
                            # Он сам подставит topic, language и т.д. в шаблон template_content
                            try:
                                en_prompt_text = selected_prompt_obj.render(
                                    topic=ai_topic_en,
                                    language="English",
                                    banned_topics="",
                                    old_context=additional_context
                                )
                                print(
                                    f"📝 [DEBUG] Промпт успешно отрендерен. Длина: {len(en_prompt_text)}")
                                print(
                                    f"📝 [DEBUG] Начало текста: {en_prompt_text[:60]}...")

                            except Exception as render_err:
                                print(f"⚠️ Ошибка рендеринга: {render_err}")
                                # Фоллбэк: просто берем сырой текст, если форматирование сломалось
                                en_prompt_text = selected_prompt_obj.template_content
                        else:
                            print(
                                f"⚠️ [DEBUG] Промпт '{prompt_code}' НЕ НАЙДЕН!")
                            en_prompt_text = f"Write an article about {ai_topic_en}. Context: {additional_context}"
                            prompt_name = "Заглушка (Default)"

                        update_progress(session_key, current_step,
                                        f"Шаблон: {prompt_name}")
                        final_system_message = en_prompt_text

                        # 2. Генерация ОСНОВНОЙ статьи (EN)
                        print(f">>> [THREAD] Генерация EN статьи...")
                        try:
                            print(
                                f">>> [DEBUG] Отправка промпта (длина: {len(final_system_message)})...")
                            en_content_raw = generate_text(
                                provider, final_system_message, max_tokens=3000)

                            print(
                                f">>> [DEBUG] === СЫРОЙ ОТВЕТ МОДЕЛИ (первые 500 символов) ===")
                            print(en_content_raw[:500])
                            print(f">>> [DEBUG] === КОНЕЦ СЫРОГО ОТВЕТА ===")

                            if "Topic unknown" in en_content_raw or "insufficiently studied" in en_content_raw:
                                raise ValueError(
                                    "AI отказался писать: тема неизвестна.")

                            if len(en_content_raw.strip()) < 20:
                                raise ValueError(
                                    f"Модель вернула пустой ответ: '{en_content_raw}'")

                            en_data = parse_ai_json(en_content_raw)

                            if not en_data.get('content') or len(en_data['content']) < 50:
                                print(
                                    f">>> [DEBUG] Распарсенные данные: {en_data}")
                                raise ValueError(
                                    f"Контент слишком короткий. Получено: {en_data.get('content', 'NONE')}")

                        except Exception as e:
                            print(f">>> [THREAD] ❌ ОШИБКА ГЕНЕРАЦИИ: {e}")
                            update_progress(
                                session_key, 0, f"Ошибка генерации: {str(e)}", status='error')
                            return  # Прерываем выполнение задачи

                        main_article = Article.objects.create(
                            title=en_data.get('title', 'Untitled'),
                            content=en_data.get('content', ''),
                            description=en_data.get('description', '')[:200],
                            hashtags=en_data.get('hashtags', ''),
                            status='draft'
                        )
                        print(
                            f">>> [THREAD] Статья создана: ID {main_article.id}")

                        # 3. Переводы (ЦИКЛ)
                        lang_en = Language.objects.get(code='en')
                        ArticleTranslation.objects.create(
                            cluster=cluster, language=lang_en,
                            title=main_article.title,
                            content=main_article.content,
                            description=main_article.description,
                            hashtags=main_article.hashtags,
                            status='draft'
                        )
                        current_step += 1
                        update_progress(session_key, current_step,
                                        "EN версия сохранена")

                        for code in selected_lang_codes:
                            if code == 'en':
                                continue

                            try:
                                lang_obj = Language.objects.get(code=code)
                                update_progress(
                                    session_key, current_step, f"Перевод на {lang_obj.name}...")

                                # --- ПРОВЕРКА: Есть ли данные для перевода? ---
                                if not en_data or not en_data.get('content'):
                                    raise ValueError(
                                        "Нет данных статьи (en_data) для перевода!")

                                # --- ПОДГОТОВКА ДАННЫХ ДЛЯ ПЕРЕВОДА ---

                                # Берем оригинальный английский заголовок
                                original_en_title = en_data.get(
                                    'title', 'Unknown Topic')

                                context = {
                                    'target_lang': lang_obj.name,
                                    'original_title': original_en_title,  # <-- Новая переменная для промпта
                                    # <-- Только текст статьи, заголовок отдельно
                                    'article_content': en_data['content']
                                }

                                # Получаем промпт из БД
                                trans_prompt = get_system_instruction(
                                    'translation_strict', context)

                                # Генерируем перевод
                                trans_raw = generate_text(
                                    provider, trans_prompt, max_tokens=2500)

                                # Парсим ответ
                                trans_data = parse_ai_json(trans_raw)

                                # Если парсинг не удался, используем оригинал
                                if not trans_data.get('content'):
                                    print(
                                        f"⚠️ Парсинг перевода {code} не удался, используем EN текст.")
                                    trans_data = {
                                        'title': en_data['title'],
                                        'content': en_data['content'],
                                        'description': en_data.get('description', ''),
                                        'hashtags': en_data.get('hashtags', '')
                                    }

                                # Сохраняем перевод
                                ArticleTranslation.objects.create(
                                    cluster=cluster, language=lang_obj,
                                    title=trans_data.get(
                                        'title', en_data['title']),
                                    content=trans_data.get('content', ''),
                                    description=trans_data.get(
                                        'description', ''),
                                    hashtags=trans_data.get('hashtags', ''),
                                    status='draft'
                                )
                                current_step += 1
                                print(f">>> [THREAD] Перевод {code} готов.")

                            except Exception as trans_err:
                                print(
                                    f">>> [THREAD] ❌ Ошибка перевода {code}: {trans_err}. Пропускаем язык.")
                                import traceback
                                traceback.print_exc()
                                continue

                        # 4. Промпты для картинок
                        if generate_prompts:
                            try:
                                update_progress(
                                    session_key, current_step, "Генерация промптов для сцен...")
                                scene_count = manual_count if img_mode == 'manual' else 4
                                context = en_data['content'][:2500]

                                splitter_prompt = f"""
Analyze the text below. Extract {scene_count} visual scenes.
Write image prompts STRICTLY IN ENGLISH.
Return JSON list: [{{"scene_description": "...", "prompt": "English prompt here --ar {aspect_ratio}"}}]

Text: {context}
"""
                                scenes_raw = generate_text(
                                    provider, splitter_prompt, max_tokens=1500)

                                clean = scenes_raw.replace(
                                    "```json", "").replace("```", "").strip()
                                scenes_data = json.loads(clean)

                                if isinstance(scenes_data, list):
                                    stype = SceneType.objects.first()
                                    count = 0
                                    for sc in scenes_data:
                                        p_text = sc.get('prompt', '')
                                        if p_text:
                                            ImagePrompt.objects.create(
                                                article=main_article, scene_type=stype,
                                                prompt_text=p_text, is_generated=False
                                            )
                                            count += 1
                                    print(
                                        f">>> [THREAD] ✅ Создано промптов: {count}")
                                    update_progress(
                                        session_key, current_step, f"Создано {count} промптов")
                                else:
                                    raise ValueError("AI вернул не список")

                            except Exception as p_err:
                                print(f">>> ⚠️ Ошибка промптов: {p_err}")
                                import traceback
                                traceback.print_exc()
                                update_progress(
                                    session_key, current_step, "Промпты не созданы (ошибка AI)")

                        # Финализация идеи
                        idea.status = 'completed'
                        idea.save()
                        cluster.is_complete = True
                        cluster.save()
                        print(
                            f">>> [THREAD] Идея {idea.id} завершена успешно.")

                    # ВСЕ УСПЕШНО
                    update_progress(
                        session_key, 100, "Готово! Перенаправление...", status='done')
                    print(">>> THREAD SUCCESS")

                except Exception as global_err:
                    print(
                        f">>> [THREAD] 💀 GLOBAL CRITICAL ERROR: {global_err}")
                    import traceback
                    traceback.print_exc()
                    update_progress(
                        session_key, 0, f"Критический сбой: {str(global_err)}", status='error')

            # Запуск потока
            threading.Thread(target=run_task, daemon=True).start()
            return JsonResponse({'status': 'started'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


def update_progress(session_key, current_step, message, status='running'):
    if session_key in ARTICLE_GEN_PROGRESS:
        total = ARTICLE_GEN_PROGRESS[session_key]['total']
        percent = int((current_step / total) * 100) if total > 0 else 0
        if percent > 100:
            percent = 100

        ARTICLE_GEN_PROGRESS[session_key].update({
            'current': current_step,
            'percent': percent,
            'message': message,
            'status': status,
            'log': ARTICLE_GEN_PROGRESS[session_key].get('log', []) + [f"{time.strftime('%H:%M:%S')}: {message}"]
        })


def generation_stream(request):
    def event_stream():
        session_key = request.session.session_key
        if not session_key:
            return
        last_percent = -1
        last_msg = ""

        while True:
            data = ARTICLE_GEN_PROGRESS.get(session_key)
            if data:
                # Отправляем только если изменились данные или это финал
                if (data['percent'] != last_percent or
                    data['message'] != last_msg or
                        data['status'] in ['done', 'error']):

                    # ВАЖНО: Формат SSE строго "data: JSON\n\n"
                    yield f"data: {json.dumps(data)}\n\n"

                    last_percent = data['percent']
                    last_msg = data['message']

                if data['status'] in ['done', 'error']:
                    time.sleep(1)  # Даем браузеру время получить пакет
                    if session_key in ARTICLE_GEN_PROGRESS:
                        del ARTICLE_GEN_PROGRESS[session_key]
                    break
            else:
                # Если данные удалились, но статус не был done/error - выходим
                if last_percent == 100 or last_msg.startswith("Критическая"):
                    break

            time.sleep(0.5)

    response = StreamingHttpResponse(
        event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    # response['Connection'] = 'keep-alive'
    return response


def clean_json_string(text):
    """
    Очищает текст от символов, ломающих JSON:
    1. Заменяет умные кавычки на обычные.
    2. Экранирует двойные кавычки внутри строки.
    3. Заменяет реальные переносы строк на \n.
    """
    if not text:
        return ""

    # 1. Замена умных кавычек и апострофов
    text = text.replace('"', '"')   # Левая двойная
    text = text.replace('"', '"')   # Правая двойная
    text = text.replace(''', "'")   # Левая одинарная
    text = text.replace(''', "'")   # Правая одинарная (апостроф)
    text = text.replace('`', "'")   # Гравис

    # ВАЖНО: Мы НЕ делаем replace('\n', '\\n') здесь,
    # так как это сломает структуру JSON (переносы между полями).
    # Если модель вставила реальный перенос строки ВНУТРИ строкового значения,
    # это нарушает стандарт JSON, но многие парсеры это прощают.
    # Если будет ошибка, мы попробуем другой метод ниже.

    return text


def parse_ai_json(text):
    if not text:
        return {}

    # 1. Чистим от маркдауна (если есть)
    text = text.replace("```json", "").replace("```", "").strip()

    # 2. НАХОДИМ JSON (от первой { до последней })
    start = text.find('{')
    end = text.rfind('}')

    if start == -1 or end == -1:
        print("❌ Нет JSON скобок")
        return {}

    # Вырезаем кусок
    json_str = text[start: end+1]

    # 3. ГЛАВНЫЙ ТРЮК: Заменяем ВСЕ реальные переносы строк на пробелы.
    # Да, текст статьи станет одной длинной строкой без абзацев,
    # НО это гарантированно спасет от ошибки "Invalid control character".
    # Абзацы можно восстановить потом заменой двойных пробелов, если нужно,
    # но для начала главное — чтобы работало.
    json_str = json_str.replace('\n', ' ').replace('\r', ' ')

    # 4. Чистим кавычки (на всякий случай)
    json_str = json_str.replace('"', '"').replace('"', '"')

    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"❌ Ошибка JSON: {e}")
        # Если не вышло — возвращаем пустоту, чтобы код не падал
        return {}


def article_dashboard(request):
    # --- УДАЛЕНИЕ И СМЕНА СТАТУСА ---
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_articles')

        if selected_ids:
            clusters = ArticleCluster.objects.filter(id__in=selected_ids)

            if action == 'delete_selected':
                count, _ = clusters.delete()
                messages.success(request, f"✅ Удалено {count} статей.")

            elif action == 'change_status':
                new_status = request.POST.get('new_status')
                if new_status:
                    # Если выбрано "published", ставим True, иначе False
                    is_complete_val = (new_status == 'published')
                    clusters.update(is_complete=is_complete_val)

                    status_text = "Опубликовано" if is_complete_val else "В работе"
                    messages.success(
                        request, f"✅ Статус изменен на «{status_text}» для {clusters.count()} статей.")
                else:
                    messages.warning(request, "⚠️ Не выбран новый статус.")
        else:
            messages.warning(request, "⚠️ Вы не выбрали ни одной статьи.")

        return redirect('article:dashboard')

    # --- ПОДГОТОВКА ДАННЫХ ---
    clusters_qs = ArticleCluster.objects.all().order_by('-created_at')

    # print(f"🔍 [DEBUG] Найдено кластеров в БД: {clusters_qs.count()}")

    prepared_clusters = []

    for cluster in clusters_qs:
        try:
            # Получаем переводы. Используем list(), чтобы сразу выполнить запрос
            translations = list(cluster.translations.all())

            main_trans = None
            for t in translations:
                if t.language.code == 'ru':
                    main_trans = t
                    break

            if not main_trans and translations:
                main_trans = translations[0]

            prepared_clusters.append({
                'instance': cluster,
                'translations': translations,
                'main_trans': main_trans,
            })
            # print(
            #     f"   ✅ Обработан кластер #{cluster.id}: {len(translations)} переводов, заголовок: {main_trans.title if main_trans else 'НЕТ'}")

        except Exception as e:
            print(f"   ❌ Ошибка при обработке кластера #{cluster.id}: {e}")

    # print(
    #     f"🚀 [DEBUG] Итоговый список для шаблона: {len(prepared_clusters)} элементов.")

    stats = {
        'total': clusters_qs.count(),
        'draft': clusters_qs.filter(is_complete=False).count(),
        'published': clusters_qs.filter(is_complete=True).count(),
    }

    return render(request, 'article/dashboard.html', {
        'articles': prepared_clusters,
        'stats': stats,
    })


def article_editor(request, pk):
    cluster = get_object_or_404(ArticleCluster, id=pk)
    translations = cluster.translations.all().order_by('language__order')

    # Безопасное получение основного перевода
    main_trans = translations.filter(language__code='ru').first()
    if not main_trans and translations.exists():
        main_trans = translations.first()

    # Обработка POST
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_translation':
            trans_id = request.POST.get('translation_id')
            if trans_id:
                trans = get_object_or_404(
                    ArticleTranslation, id=trans_id, cluster=cluster)
                trans.title = request.POST.get('title')
                trans.content = request.POST.get('content')
                trans.description = request.POST.get('description')
                trans.hashtags = request.POST.get('hashtags')
                trans.save()
                messages.success(request, "Сохранено!")
                return redirect('article:article_editor', pk=cluster.id)

        elif action == 'update_cluster_status':
            cluster.is_complete = request.POST.get('is_complete') == 'on'
            cluster.save()
            messages.success(request, "Статус обновлен!")
            return redirect('article:article_editor', pk=cluster.id)

    context = {
        'cluster': cluster,
        'translations': translations,
        'main_trans': main_trans,
        # 'all_languages': Language.objects.filter(is_active=True), # Можно убрать, если не используем для добавления
    }
    return render(request, 'article/editor.html', context)
