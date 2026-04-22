import json
from datetime import timedelta
from django.utils import timezone
from .models import VideoProject
# Импортируем нашу универсальную функцию из ai_inspector
from ai_inspector.services import generate_text


def generate_unique_ideas(provider_name='huggingface', count=3, topic="История",
                          focus_topics=None, refresh_old=False, refresh_days=None,
                          allow_duplicates=False, no_duplicate_days=None):
    """
    Генерирует идеи, используя указанный AI провайдер.
    """
    print(f"🤖 Запуск генерации через: {provider_name}")
    print(f" Тема: {topic}, Фокус: {focus_topics}")

    # --- 1. Сбор контекста (запрещенные темы) ---
    banned_list = []

    # Логика запрета повторов
    if not allow_duplicates and no_duplicate_days:
        cutoff_date = timezone.now() - timedelta(days=no_duplicate_days)
        recent_ideas = VideoProject.objects.filter(created_at__gte=cutoff_date)
        for idea in recent_ideas:
            banned_list.append(f"- {idea.topic}: {idea.angle}")
    else:
        # Если повторы разрешены, все равно дадим модели контекст последних идей
        recent_ideas = VideoProject.objects.order_by('-created_at')[:50]
        for idea in recent_ideas:
            banned_list.append(
                f"- {idea.topic}: {idea.angle} (МОЖНО ПОВТОРИТЬ)")

    # Логика обновления старых
    old_ideas_context = ""
    if refresh_old and refresh_days:
        old_cutoff = timezone.now() - timedelta(days=refresh_days)
        old_ideas = VideoProject.objects.filter(created_at__lt=old_cutoff)[:10]
        if old_ideas:
            old_ideas_context = "\nСПИСОК СТАРЫХ ИДЕЙ ДЛЯ ОБНОВЛЕНИЯ (ПРЕДЛОЖИ НОВЫЙ УГОЛ):\n"
            for idea in old_ideas:
                old_ideas_context += f"- Старая: {idea.angle} (Тема: {idea.topic})\n"

    banned_context = "\n".join(banned_list) if banned_list else "База пуста."

    # --- 2. Формирование Промпта ---
    system_prompt = f"""Ты — продюсер TikTok-канала. Задача: придумать {count} уникальных идей.
    
ОБЩАЯ ТЕМА: {topic}
{"ФОКУСНЫЕ ТЕМЫ (СТРОГО ПРИДЕРЖИВАЙСЯ): " + ", ".join(focus_topics) if focus_topics else ""}

ВАЖНЫЕ ПРАВИЛА:
1. ИЗБЕГАЙ повторения со списком ниже (если не указано иное):
{banned_context}

{old_ideas_context}

2. Верни ответ СТРОГО в формате JSON массива. Без лишнего текста.
3. Язык сценария: Русский.
4. Стиль: Кликбейтный, динамичный.

Формат JSON:
[
  {{
    "topic": "Краткая тема",
    "angle": "Цепляющий заголовок",
    "notes": "Сценарий на русском...",
    "status": "new"
  }}
]
"""

    try:
        # !!! ГЛАВНЫЙ ВЫЗОВ С НОВЫМ АРГУМЕНТОМ !!!
        # Теперь мы передаем provider_name первым аргументом
        response_text = generate_text(
            provider_name, system_prompt, max_tokens=1500)

        print("📥 Ответ получен. Парсинг JSON...")

        # Очистка JSON от мусора
        clean_json = response_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        ideas_data = json.loads(clean_json)

        # --- 3. Сохранение в БД ---
        saved_count = 0
        for item in ideas_data:
            angle = item.get('angle', '')

            # Финальная проверка на дубли перед сохранением
            if not allow_duplicates and no_duplicate_days:
                if VideoProject.objects.filter(angle=angle).exists():
                    print(f"️ Пропущен дубль: {angle}")
                    continue

            VideoProject.objects.create(
                topic=item.get('topic', topic),
                angle=angle,
                notes=item.get('notes', ''),
                status='new'
            )
            saved_count += 1
            print(f"✅ Сохранено: {angle}")

        print(f"🎉 Итог: сохранено {saved_count} идей.")
        return saved_count

    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        print(f"Сырой ответ: {response_text[:500]}...")
        raise Exception(f"Модель вернула некорректный JSON: {str(e)}")

    except Exception as e:
        print(f"❌ Критическая ошибка в сервисе: {e}")
        raise e
