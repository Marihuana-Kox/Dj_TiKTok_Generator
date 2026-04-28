import json
import time
import threading
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib import messages

# Импорт моделей
from prompts.models import ArticlePrompt, StructurePlanPrompt
from topics.models import VideoProject
from article.models import Article, ArticleCluster, ArticleTranslation, ImagePrompt, Language, SceneType
from article.forms import ArticleGenerationForm

# Импорт сервисов
from ai_inspector.services import generate_text
from prompts.services import render_article_prompt, render_structure_prompt

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
                        print(
                            f">>> [DEBUG] Контекст (факты): {additional_context[:100]}...")

                        # --- ПРОМПТ СТАТЬИ ---
                        if prompt_code == 'random':
                            selected_prompt_obj = ArticlePrompt.objects.filter(
                                is_active=True).order_by('?').first()
                            prompt_name = "Случайный стиль"
                        else:
                            selected_prompt_obj = ArticlePrompt.objects.filter(
                                code_name=prompt_code, is_active=True).first()
                            prompt_name = prompt_code or "Базовый"

                        if selected_prompt_obj:
                            en_prompt_text = render_article_prompt(
                                style_code=selected_prompt_obj.code_name,
                                topic=ai_topic_en,          # Используем английский вариант
                                language="English",
                                banned_topics="",
                                old_context=additional_context  # Передаем факты и вопросы
                            )
                        else:
                            en_prompt_text = f"Write an article about {ai_topic_en}. Context: {additional_context}"
                            prompt_name = "Без шаблона"

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
                                f">>> [DEBUG] === СЫРОЙ ОТВЕТ МОДЕЛИ (первые 1000 символов) ===")
                            print(en_content_raw[:1000])
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

                                trans_prompt = f"Translate to {lang_obj.name}. Return JSON: title, content, description, hashtags.\nOriginal:\n{en_data['content']}"
                                trans_raw = generate_text(
                                    provider, trans_prompt, max_tokens=2500)

                                trans_data = parse_ai_json(trans_raw)

                                if not trans_data.get('content'):
                                    print(
                                        f">>> [THREAD] ⚠️ Парсинг перевода {code} не удался, используем EN текст.")
                                    trans_data = {
                                        'title': main_article.title,
                                        'content': main_article.content,
                                        'description': main_article.description,
                                        'hashtags': main_article.hashtags
                                    }

                                ArticleTranslation.objects.create(
                                    cluster=cluster, language=lang_obj,
                                    title=trans_data.get(
                                        'title', main_article.title),
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


def parse_ai_json(text):
    try:
        clean_text = text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"JSON Parse Error: {e}")
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
                    messages.success(request, f"✅ Статус изменен на «{status_text}» для {clusters.count()} статей.")
                else:
                    messages.warning(request, "⚠️ Не выбран новый статус.")
        else:
            messages.warning(request, "⚠️ Вы не выбрали ни одной статьи.")
            
        return redirect('article:dashboard')

    # --- ПОДГОТОВКА ДАННЫХ ---
    clusters_qs = ArticleCluster.objects.all().order_by('-created_at')
    
    print(f"🔍 [DEBUG] Найдено кластеров в БД: {clusters_qs.count()}")
    
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
            print(f"   ✅ Обработан кластер #{cluster.id}: {len(translations)} переводов, заголовок: {main_trans.title if main_trans else 'НЕТ'}")
            
        except Exception as e:
            print(f"   ❌ Ошибка при обработке кластера #{cluster.id}: {e}")

    print(f"🚀 [DEBUG] Итоговый список для шаблона: {len(prepared_clusters)} элементов.")

    stats = {
        'total': clusters_qs.count(),
        'draft': clusters_qs.filter(is_complete=False).count(),
        'published': clusters_qs.filter(is_complete=True).count(),
    }

    return render(request, 'article/dashboard.html', {
        'articles': prepared_clusters,
        'stats': stats,
    })
# def article_dashboard(request):
#     if request.method == 'POST':
#         action = request.POST.get('action')
#         if action == 'delete_selected':
#             selected_ids = request.POST.getlist('selected_articles')
#             if selected_ids:
#                 count, _ = ArticleCluster.objects.filter(id__in=selected_ids).delete()
#                 messages.success(request, f"✅ Удалено {count} статей.")
#             else:
#                 messages.warning(request, "⚠️ Вы не выбрали ни одной статьи.")
#             return redirect('article:dashboard')
#     # --- ПОДГОТОВКА ДАННЫХ ---
#     # 1. Получаем все кластеры
#     clusters_qs = ArticleCluster.objects.all().order_by('-created_at')

#     prepared_clusters = []
    
#     for cluster in clusters_qs:
#         # Получаем все переводы для этого кластера (сразу в список)
#         translations = list(cluster.translations.all())
        
#         # Ищем русский перевод или берем первый попавшийся
#         main_trans = None
#         for t in translations:
#             if t.language.code == 'ru':
#                 main_trans = t
#                 break
        
#         # Если русского нет, берем первый из списка
#         if not main_trans and translations:
#             main_trans = translations[0]
            
#         prepared_clusters.append({
#             'instance': cluster,
#             'translations': translations,      # Готовый список переводов
#             'main_trans': main_trans,          # Главный перевод (RU или первый)
#             'has_ru': main_trans and main_trans.language.code == 'ru'
#         })

#     stats = {
#         'total': clusters_qs.count(),
#         'draft': clusters_qs.filter(is_complete=False).count(),
#         'published': clusters_qs.filter(is_complete=True).count(),
#     }

#     return render(request, 'article/dashboard.html', {'clusters': prepared_clusters, 'stats': stats})


def article_editor(request, pk):
    """Страница редактирования статьи и её переводов"""
    main_article = get_object_or_404(Article, pk=pk)
    translations_qs = ArticleTranslation.objects.filter(
        title=main_article.title).select_related('language')
    trans_dict = {t.language.code: t for t in translations_qs}

    if request.method == 'POST':
        main_article.title = request.POST.get('title_en', main_article.title)
        main_article.content = request.POST.get(
            'content_en', main_article.content)
        main_article.description = request.POST.get(
            'description_en', main_article.description)
        main_article.hashtags = request.POST.get(
            'hashtags_en', main_article.hashtags)
        main_article.save()

        langs_to_check = ['ru', 'de', 'fr', 'es']
        for lang_code in langs_to_check:
            if lang_code in trans_dict:
                t_obj = trans_dict[lang_code]
                t_obj.title = request.POST.get(
                    f'title_{lang_code}', t_obj.title)
                t_obj.content = request.POST.get(
                    f'content_{lang_code}', t_obj.content)
                t_obj.description = request.POST.get(
                    f'description_{lang_code}', t_obj.description)
                t_obj.hashtags = request.POST.get(
                    f'hashtags_{lang_code}', t_obj.hashtags)
                t_obj.save()

        messages.success(
            request, f"✅ Статья '{main_article.title}' успешно обновлена!")
        return redirect('article:dashboard')

    context = {
        'article': main_article,
        'translations': trans_dict,
    }
    return render(request, 'article/edit.html', context)
