import json
from datetime import timedelta
from django.utils import timezone
from .models import VideoProject
from ai_inspector.services import generate_text

# ПРОВЕРКА ИМПОРТА НА УРОВНЕ МОДУЛЯ (Вне функции)
try:
    from prompts.services import render_idea_prompt
    DEFAULT_PROMPTS_ENABLED = True
except ImportError:
    DEFAULT_PROMPTS_ENABLED = False
    print("⚠️ Prompts app not found. Using fallback logic.")


def generate_unique_ideas(provider_name='huggingface', count=3, topic="История",
                          focus_topics=None, idea_style='facts', refresh_old=False, refresh_days=None,
                          allow_duplicates=False, no_duplicate_days=None, callback=None):
    """
    Генерирует идеи поштучно.
    Логика: Входная строка -> Категория. AI придумывает конкретный сюжет внутри категории.
    """
    # Используем глобальный флаг
    prompts_enabled = DEFAULT_PROMPTS_ENABLED

    print(f"🤖 Запуск генерации через: {provider_name}")
    print(f"🎨 Стиль промпта: {idea_style}")
    print(f"📝 Промпты из БД включены: {prompts_enabled}")
    print(
        f"📝 Темы (Категории): {focus_topics if focus_topics else 'Случайные'}")

    # --- 0. Создание заготовок со статусом PENDING ---
    print(f"📝 Создание {count} заготовок...")
    idea_objects = []
    for i in range(count):
        obj = VideoProject.objects.create(
            topic=f"Генерация #{i+1}...",
            angle=f"Ожидание AI...",
            notes="",
            status='pending'  # Статус ожидания
        )
        idea_objects.append(obj)
        if callback:
            callback(current=i+1, total=count, step="create_queue",
                     message=f"Queue #{i+1}", idea_id=obj.id)

    # --- 1. Сбор контекста (banned_list) ---
    banned_list = []
    if not allow_duplicates and no_duplicate_days:
        cutoff_date = timezone.now() - timedelta(days=no_duplicate_days)
        recent_ideas = VideoProject.objects.filter(created_at__gte=cutoff_date)
        for idea in recent_ideas:
            banned_list.append(f"- {idea.topic}: {idea.angle}")
    else:
        recent_ideas = VideoProject.objects.order_by('-created_at')[:50]
        for idea in recent_ideas:
            banned_list.append(f"- {idea.topic}: {idea.angle} (OK)")

    banned_context = "\n".join(
        banned_list) if banned_list else "No restrictions."

    old_ideas_context = ""
    if refresh_old and refresh_days:
        old_cutoff = timezone.now() - timedelta(days=refresh_days)
        old_ideas = VideoProject.objects.filter(created_at__lt=old_cutoff)[:10]
        if old_ideas:
            old_ideas_context = "\nOLD IDEAS TO REFRESH:\n"
            for idea in old_ideas:
                old_ideas_context += f"- {idea.angle}\n"

    try:
        saved_count = 0
        topics_to_process = []

        if focus_topics:
            for i in range(count):
                topics_to_process.append(focus_topics[i % len(focus_topics)])
        else:
            topics_to_process = [f"Idea #{i+1}" for i in range(count)]

        for index, idea_obj in enumerate(idea_objects):
            current_num = index + 1
            current_topic_string = topics_to_process[index]

            if callback:
                callback(current=current_num, total=count, step="generating",
                         message=f"Processing: {current_topic_string}...", idea_id=idea_obj.id)

            system_prompt = ""

            # Попытка получить промпт из БД
            if prompts_enabled:
                try:
                    system_prompt = render_idea_prompt(
                        style_code=idea_style,
                        topic=current_topic_string,
                        banned_topics=banned_context,
                        old_context=old_ideas_context,
                        language="Russian"
                    )
                except Exception as e:
                    print(f"⚠️ Prompt DB error: {e}. Switching to fallback.")
                    prompts_enabled = False

            # Fallback промпт, если БД недоступна
            if not system_prompt:
                system_prompt = f"""You are an expert Creative Director.
INPUT CATEGORY: "{current_topic_string}".
TASK: Invent a SPECIFIC story within this category.
Return JSON with keys: 'specific_topic', 'summary', 'facts', 'questions'. Language: Russian."""

            try:
                response_text = generate_text(
                    provider_name, system_prompt, max_tokens=800)

                clean_json = response_text.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                if clean_json.startswith("[") and clean_json.endswith("]"):
                    clean_json = clean_json[1:-1]

                data = json.loads(clean_json)

                # --- НОВАЯ ЛОГИКА РАСПРЕДЕЛЕНИЯ ПОЛЕЙ ---

                # 1. Angle (Заголовок идеи) = Конкретный сюжет от AI
                # Приоритет полю 'specific_topic', которое мы просим в новом промпте
                final_angle = data.get('specific_topic', '')

                if not final_angle:
                    # Если модель старая и не вернула specific_topic, пробуем скомбинировать
                    summary = data.get('summary', 'New Story')
                    final_angle = f"{current_topic_string}: {summary[:50]}"

                # 2. Topic (Рубрика) = Твой исходный запрос (Категория)
                # Очищаем, но оставляем смысл
                category = current_topic_string.strip()
                if len(category) > 60:
                    category = category[:57] + "..."

                # 3. Notes (Факты и Вопросы)
                ai_summary = data.get('summary', '')
                facts_list = data.get('facts', [])
                questions_list = data.get('questions', [])

                notes_content = f"=== СУТЬ СЮЖЕТА ===\n{ai_summary}\n\n"
                notes_content += "=== КОНКРЕТНЫЕ ФАКТЫ ===\n"
                for f in facts_list:
                    notes_content += f"- {f}\n"
                notes_content += "\n=== ВОПРОСЫ ДЛЯ СТАТЬИ ===\n"
                for q in questions_list:
                    notes_content += f"- {q}\n"

                # --- СОХРАНЕНИЕ В БД ---
                # Твоя категория ("Загадки истории")
                idea_obj.topic = category
                # Конкретная идея AI ("Тайны бункера")
                idea_obj.angle = final_angle
                idea_obj.notes = notes_content.strip()
                # ✅ СТАТУС МЕНЯЕМ НА 'new' (ГОТОВО)
                idea_obj.status = 'new'
                idea_obj.save()

                saved_count += 1
                print(f"✅ Создана идея: [{category}] -> {final_angle}")

                if callback:
                    callback(current=current_num, total=count, step="saved",
                             message=f"Готово: {final_angle}", idea_id=idea_obj.id)

            except Exception as e:
                err_msg = str(e)
                print(f"❌ Error for '{current_topic_string}': {err_msg}")
                if callback:
                    callback(current=current_num, total=count, step="error",
                             message=f"Error: {err_msg[:30]}", idea_id=idea_obj.id)

                # При ошибке сохраняем как rejected, но сохраняем тему
                idea_obj.topic = "Ошибка генерации"
                idea_obj.angle = current_topic_string
                idea_obj.notes = f"Generation failed: {err_msg}"
                idea_obj.status = 'rejected'
                idea_obj.save()
                continue

        print(f"🎉 Итог: успешно создано {saved_count} идей.")
        return saved_count

    except Exception as e:
        print(f"❌ Critical service error: {e}")
        raise e
