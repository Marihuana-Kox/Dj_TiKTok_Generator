import json
import random
from pathlib import Path
from django.conf import settings

# Путь к JSON файлу с шаблонами
templates_file = settings.SMART_QUERIES


def load_search_templates() -> dict:
    """Загружает шаблоны поисковых запросов из JSON файла."""
    try:
        with open(templates_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Ошибка загрузки search templates: {e}")
        # Fallback: базовые шаблоны
        return {
            "categories": {
                "general": {
                    "label": "🌍 Общая",
                    "templates": [
                        "{topic} mysteries",
                        "{topic} unexplained",
                        "{topic} controversies",
                    ],
                }
            },
            "default_category": "general",
            "max_queries_per_category": 3,
        }


def get_category_choices() -> list:
    """Возвращает список кортежей (key, label) для формы."""
    data = load_search_templates()
    categories = data.get("categories", {})
    return [(key, cat["label"]) for key, cat in categories.items()]


def generate_search_queries(
    topic: str,
    category: str = "general",
    focus_notes: str = "",
    count: int = None,
    randomize: bool = True,
) -> list:
    """
    Генерирует список поисковых запросов для Tavily на основе категории и шаблонов.

    Args:
        topic: Тема исследования
        category: Категория шаблонов (person, event, architecture, artifact, general)
        focus_notes: Дополнительные указания (добавляются к каждому запросу)
        count: Количество запросов (по умолчанию из JSON)
        randomize: Если True — выбирает случайные шаблоны, иначе — первые N

    Returns:
        Список поисковых запросов (каждый до 400 символов)
    """
    data = load_search_templates()
    categories = data.get("categories", {})
    max_queries = count or data.get("max_queries_per_category", 6)

    # Получаем шаблоны для выбранной категории
    if category not in categories:
        print(f"⚠️ Категория '{category}' не найдена. Используем 'general'.")
        category = "general"

    category_data = categories[category]
    templates = category_data.get("templates", [])

    if not templates:
        print("⚠️ Шаблоны не найдены. Используем базовый запрос.")
        return [f"{topic} mysteries unexplained"]

    # Выбираем шаблоны
    if randomize and len(templates) > max_queries:
        selected_templates = random.sample(templates, max_queries)
    else:
        selected_templates = templates[:max_queries]

    # Формируем запросы
    queries = []
    focus_suffix = f". {focus_notes}" if focus_notes and focus_notes.strip() else ""

    for template in selected_templates:
        # Подставляем тему
        query = template.replace("{topic}", topic.strip())

        # Добавляем фокус, если есть
        if focus_suffix:
            query += focus_suffix

        # Обрезаем до 400 символов (лимит Tavily)
        if len(query) > 400:
            query = query[:400].rsplit(" ", 1)[0]

        queries.append(query)

    print(f"🎯 [TEMPLATES] Категория: {category_data.get('label', category)}")
    print(f"🎯 [TEMPLATES] Сгенерировано {len(queries)} поисковых запросов:")
    for i, q in enumerate(queries, 1):
        print(f"   {i}. {q}")

    return queries
