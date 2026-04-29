import json
import re
import traceback
from datetime import timedelta
from django.utils import timezone
from .models import VideoProject
from ai_inspector.services import generate_text
from prompts.services import get_random_idea_prompt

# ПРОВЕРКА ИМПОРТА НА УРОВНЕ МОДУЛЯ
try:
    from prompts.services import render_idea_prompt
    DEFAULT_PROMPTS_ENABLED = True
except ImportError:
    DEFAULT_PROMPTS_ENABLED = False
    print("⚠️ Prompts app not found. Using fallback logic.")


def clean_ai_string(text):
    """
    Очищает строку от лишней болтовни AI (преамбулы, комментарии, пояснения).
    Оставляет только суть заголовка или текста.
    """
    if not text:
        return ""

    s = text.strip()

    # 1. Удаляем маркдаун блоки если остались
    if s.startswith("```"):
        s = re.sub(r'^```.*?\n', '', s, flags=re.DOTALL)
    if s.endswith("```"):
        s = s.rsplit('```', 1)[0]

    s = s.strip()

    # 2. Список префиксов, которые часто лепит AI
    prefixes = [
        "the translated title is:", "translation:", "english:",
        "here is the english translation:", "title:", "angle_en:",
        "the title in english is:", "translated as:", "i suggest:"
    ]

    s_lower = s.lower()
    for p in prefixes:
        if s_lower.startswith(p):
            s = s[len(p):].strip()
            break

    # 3. Удаляем постфиксы и комментарии внутри строки (часто бывает после двоеточия или слова However)
    stop_words = ["However", "Note that", "It seems",
                  "But", "Also,", "Explanation:", "Comment:"]
    for stop in stop_words:
        if stop in s:
            s = s.split(stop)[0].strip()

    # 4. Убираем лишние кавычки в начале и конце
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]

    # 5. Обрезаем хвосты типа ": (incomplete)"
    if s.endswith(":"):
        s = s[:-1]

    return s.strip()


def generate_unique_ideas(provider_name='huggingface', count=3, topic="История",
                          focus_topics=None, idea_style='facts', refresh_old=False, refresh_days=None,
                          allow_duplicates=False, no_duplicate_days=None, callback=None):
    """
    Генерирует идеи поштучно с поддержкой двух языков (RU для UI, EN для AI).
    """
    prompts_enabled = DEFAULT_PROMPTS_ENABLED

    print(f"🤖 Запуск генерации через: {provider_name}")
    print(f"🎨 Стиль промпта: {idea_style}")
    print(f"📝 Промпты из БД включены: {prompts_enabled}")

    # --- 0. Создание заготовок ---
    print(f"📝 Создание {count} заготовок...")
    idea_objects = []
    for i in range(count):
        obj = VideoProject.objects.create(
            topic=f"Генерация #{i+1}...",
            angle=f"Ожидание AI...",
            notes="",
            status='pending'
        )
        idea_objects.append(obj)
        if callback:
            callback(current=i+1, total=count, step="create_queue",
                     message=f"Queue #{i+1}", idea_id=obj.id)

    # --- 1. Сбор контекста ---
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
                    if idea_style == 'random':
                        obj = get_random_idea_prompt()  # 1. Добавили скобки () для вызова
                        if obj:                         # 2. Проверка: если промпт найден
                            idea_style = obj.code_name  # Берем код
                            print(f"✅ Случайный промпт найден: '{idea_style}'")
                        else:
                            # Если нет — сразу в fallback
                            raise ValueError("Нет активных промптов")

                    system_prompt = render_idea_prompt(
                        style_code=idea_style,
                        topic=current_topic_string,
                        banned_topics=banned_context,
                        old_context=old_ideas_context,
                        language="English"
                    )
                    print(f"✅ Промпт отрендерен для стиля '{idea_style}'")

                except Exception as e:
                    print(f"⚠️ Prompt DB error: {e}. Switching to fallback.")
                    prompts_enabled = False
                    system_prompt = None  # Важно обнулить, чтобы сработал блок ниже

            # Fallback промпт, если БД недоступна
            if not system_prompt:
                print("⚠️ Используем Дефолтный промпт.")
                system_prompt = f"""You are an expert Creative Director.
INPUT CATEGORY: "{current_topic_string}".
TASK: Invent a SPECIFIC story within this category.
Return ONLY a valid JSON object. No extra text. No comments.
Keys:
'topic_en' (Category in English),
'topic_ru' (Category in Russian),
'angle_en' (Catchy Title in Russian, clean string),
'summary' (in Russian),
'facts' (list of 3 strings in Russian),
'questions' (list of 2 strings in Russian).
Language for summary/facts/questions: Russian. Titles must be clean."""

            try:
                response_text = generate_text(
                    provider_name, system_prompt, max_tokens=1000)

                clean_json = response_text.strip()

                # Очистка от маркдаун блоков
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                if clean_json.startswith("[") and clean_json.endswith("]"):
                    clean_json = clean_json[1:-1]

                # Попытка найти JSON внутри текста, если модель добавила пояснения
                match = re.search(r'\{.*\}', clean_json, re.DOTALL)
                if match:
                    clean_json = match.group()

                data = json.loads(clean_json)

                # --- ИЗВЛЕЧЕНИЕ И ОЧИСТКА ДАННЫХ ---

                # 1. Тема (Рубрика)
                category_ru = clean_ai_string(
                    data.get('topic_ru', current_topic_string))
                category_en = clean_ai_string(
                    data.get('topic_en', category_ru))

                # 2. Заголовок (Angle)
                raw_angle_ru = data.get('angle_ru', '')
                raw_angle_en = data.get('angle_en', '')

                final_angle_ru = clean_ai_string(raw_angle_ru)
                final_angle_en = clean_ai_string(raw_angle_en)

                # Фоллбэк: если модель не вернула заголовки, используем summary
                if not final_angle_ru and not final_angle_en:
                    summary = clean_ai_string(data.get('summary', 'New Story'))
                    final_angle_ru = f"{category_ru}: {summary[:50]}"

                # Фоллбэк: если нет английского перевода, делаем микро-запрос
                if final_angle_ru and not final_angle_en:
                    try:
                        print(
                            f"   -> Переводим заголовок на EN: {final_angle_ru[:30]}...")
                        trans_prompt = f"Translate this title to English ONLY. No extra text: '{final_angle_ru}'"
                        final_angle_en = clean_ai_string(generate_text(
                            provider_name, trans_prompt, max_tokens=60))
                    except Exception as e:
                        print(f"   ⚠️ Ошибка перевода: {e}")
                        final_angle_en = final_angle_ru  # Оставляем русский как крайний вариант

                # Фоллбэк: если нет русского (редко), переводим с английского
                if final_angle_en and not final_angle_ru:
                    try:
                        trans_prompt = f"Translate this title to Russian ONLY. No extra text: '{final_angle_en}'"
                        final_angle_ru = clean_ai_string(generate_text(
                            provider_name, trans_prompt, max_tokens=60))
                    except:
                        final_angle_ru = final_angle_en

                # 3. Notes (Факты и Вопросы + СПЕЦ. МЕТКА ДЛЯ AI)
                ai_summary = clean_ai_string(data.get('summary', ''))
                facts_list = data.get('facts', [])
                questions_list = data.get('questions', [])

                # Формируем заметки
                notes_content = f"AI_TOPIC_EN: {final_angle_en}\n\n"
                notes_content += f"=== СУТЬ СЮЖЕТА ===\n{ai_summary}\n\n"
                notes_content += "=== КОНКРЕТНЫЕ ФАКТЫ ===\n"
                for f in facts_list:
                    notes_content += f"- {clean_ai_string(f)}\n"
                notes_content += "\n=== ВОПРОСЫ ДЛЯ СТАТЬИ ===\n"
                for q in questions_list:
                    notes_content += f"- {clean_ai_string(q)}\n"

                # --- СОХРАНЕНИЕ В БД ---
                idea_obj.topic = category_ru if category_ru else current_topic_string
                idea_obj.angle = final_angle_ru if final_angle_ru else "New Idea"
                idea_obj.notes = notes_content.strip()
                idea_obj.status = 'new'
                # Убедись, что имя поля (prompt_code) совпадает с тем, что ты создал в модели
                if hasattr(idea_obj, 'idea_style'):
                    print(
                        f"🔍 DEBUG: Сохраняем в prompt_code значение: '{idea_style}'")
                    idea_obj.idea_style = idea_style
                idea_obj.save()

                saved_count += 1
                print(
                    f"✅ Создана идея: [{idea_obj.topic}] -> {idea_obj.angle} | EN: {final_angle_en}")

                if callback:
                    callback(current=current_num, total=count, step="saved",
                             message=f"Готово: {idea_obj.angle}", idea_id=idea_obj.id)

            except Exception as e:
                err_msg = str(e)
                print(f"❌ Error for '{current_topic_string}': {err_msg}")
                if callback:
                    callback(current=current_num, total=count, step="error",
                             message=f"Error: {err_msg[:30]}", idea_id=idea_obj.id)

                idea_obj.topic = "Ошибка генерации"
                idea_obj.angle = current_topic_string
                idea_obj.notes = f"Generation failed: {err_msg}"
                idea_obj.status = 'rejected'  # Исправлено на стандартный статус
                idea_obj.save()

        print(f"🎉 Итог: успешно создано {saved_count} идей.")
        return saved_count

    except Exception as e:
        print(f"❌ Критическая ошибка в generate_unique_ideas: {e}")
        raise
