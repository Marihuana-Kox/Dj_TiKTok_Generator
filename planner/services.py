import json
import logging
import re
from prompts.models import IdeaPrompt  # Или IdeaPrompt, если промпты лежат там
from ai_inspector.services import generate_text

# Настрой логгер под свой проект (обычно выносится в settings)
logger = logging.getLogger(__name__)


class StoryPlanValidationError(ValueError):
    """Исключение для ошибок валидации сюжетного плана"""

    pass


def generate_story_plan(research_project, provider_name: str) -> dict:
    """
    Генерирует сюжетный план на основе данных исследования.
    Включает жесткое логирование для отлова подмены контекста и галлюцинаций LLM.
    """
    # 1. Получаем промпт из БД
    try:
        prompt_obj = IdeaPrompt.objects.filter(code_name="story_planner", is_active=True).first()
        if not prompt_obj:
            raise StoryPlanValidationError("Активный промпт 'story_planner' не найден в БД.")

        prompt_text_raw = getattr(
            prompt_obj, "template_content", getattr(prompt_obj, "prompt_text", "")
        )
        if not prompt_text_raw:
            raise StoryPlanValidationError(
                "В объекте промпта не найдено поле с текстом (template_content или prompt_text)."
            )

        # 🚨 ЛОГ №1: Проверяем, ЧТО РЕАЛЬНО лежит в research_project перед отправкой в промпт
        logger.warning("=== [LLM INPUT CHECK] ===")
        logger.warning(f"Project ID: {getattr(research_project, 'id', 'Unknown')}")

        # Безопасно тащим данные исследования
        r_data = getattr(research_project, "research_data", {})
        logger.warning(
            f"Raw research_data keys: {list(r_data.keys()) if isinstance(r_data, dict) else 'Not a dict'}"
        )

        research_json_str = json.dumps(r_data, ensure_ascii=False, indent=2)

        # Дамп первых 300 символов, чтобы увидеть, Петра там или вакцина, без забивания логов
        logger.warning(f"Snippet of research_json_str sent to LLM:\n{research_json_str[:300]}")
        logger.warning("=========================")

        prompt_text = prompt_text_raw.replace("{research_json}", research_json_str)

    except Exception as e:
        logger.error(f"Ошибка подготовки промпта: {e}", exc_info=True)
        raise StoryPlanValidationError(f"Ошибка подготовки промпта: {e}")

    # 2. Вызов LLM
    try:
        raw_response = generate_text(
            provider_name=provider_name,
            prompt=prompt_text,
            max_tokens=3000,
            temperature=0.7,
        )

        # 🚨 ЛОГ №2: Смотрим, что НА САМОМ ДЕЛЕ выплюнула модель до всех очисток
        logger.warning("=== [LLM RAW RESPONSE] ===")
        logger.warning(raw_response[:500])  # Смотрим начало ответа
        logger.warning("==========================")

    except Exception as e:
        logger.error(f"Ошибка при вызове generate_text: {e}", exc_info=True)
        raise

    # 3. Очистка и парсинг JSON
    cleaned = raw_response.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

    if not match:
        logger.error(f"AI не вернул JSON. Сырой ответ был: {raw_response}")
        raise StoryPlanValidationError("AI не вернул JSON объект.")

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.error(f"Парсинг JSON упал. Строка матча: {match.group(0)[:200]}")
        raise StoryPlanValidationError(f"AI вернул невалидный JSON: {e}")

    # 4. БЕЗОПАСНАЯ НОРМАЛИЗАЦИЯ
    if not isinstance(data, dict):
        raise StoryPlanValidationError("Корневой элемент ответа должен быть объектом (dict).")

    # 🔥 ИСПРАВЛЕНИЕ №1: ПРОВЕРКА НА СООТВЕТСТВИЕ ТЕМЫ (защита от галлюцинаций)
    research_topic = getattr(research_project, "topic", "").lower()
    central_mystery = str(data.get("central_mystery", "")).lower()
    hook_fact = str(data.get("hook_fact", {}).get("fact", "")).lower()

    # Берём ключевые слова из темы (слова длиннее 3 символов)
    topic_words = [word for word in research_topic.split() if len(word) > 3]

    # Проверяем, есть ли хотя бы одно ключевое слово в ответе LLM
    found_in_mystery = any(word in central_mystery for word in topic_words)
    found_in_hook = any(word in hook_fact for word in topic_words)

    if not found_in_mystery and not found_in_hook:
        logger.error(
            f"⚠️ LLM вернул данные не по теме! "
            f"Ожидается: '{research_project.topic}', "
            f"получено central_mystery: '{data.get('central_mystery', '')[:100]}'"
        )
        raise StoryPlanValidationError(
            f"LLM вернул данные не по теме. "
            f"Ожидается тема: '{research_project.topic}', "
            f"но получен central_mystery: '{data.get('central_mystery', '')[:100]}'"
        )

    data.setdefault("story_type", "Unknown")
    data.setdefault("central_mystery", str(data.get("central_mystery", "")))
    data.setdefault("hook_fact", {"fact": "", "selection_reason": ""})

    data.setdefault(
        "story_structure",
        {
            "hook": {"beat": "", "associated_images": [], "image_generation_prompt": None},
            "setup": {"beat": "", "associated_images": [], "image_generation_prompt": None},
            "development": [],
            "reveal": {"beat": "", "associated_images": [], "image_generation_prompt": None},
            "climax": {"beat": "", "associated_images": [], "image_generation_prompt": None},
            "ending": {"beat": "", "associated_images": [], "image_generation_prompt": None},
        },
    )
    data.setdefault("selected_facts", [])
    data.setdefault("discarded_facts", [])

    try:
        data["virality_score"] = int(float(data.get("virality_score", 5) or 5))
    except (ValueError, TypeError):
        data["virality_score"] = 5

    data["narrative_style"] = str(data.get("narrative_style", "DOCUMENTARY")).upper()

    if not isinstance(data["selected_facts"], list):
        data["selected_facts"] = []

    normalized_facts = []
    seen_facts = set()  # 🔥 ИСПРАВЛЕНИЕ №2: Для отслеживания дубликатов

    for fact in data["selected_facts"]:
        if not isinstance(fact, dict):
            continue

        normalized_fact = {
            "fact": str(fact.get("fact", "")).strip(),
            "role": str(fact.get("role", "development")).strip(),
            "selection_reason": str(fact.get("selection_reason", "")).strip(),
            "why_it_increases_retention": str(fact.get("why_it_increases_retention", "")).strip(),
        }

        try:
            normalized_fact["visual_priority"] = int(float(fact.get("visual_priority", 5) or 5))
        except (ValueError, TypeError):
            normalized_fact["visual_priority"] = 5

        # 🔥 ИСПРАВЛЕНИЕ №3: Пропускаем пустые факты и дубликаты
        if not normalized_fact["fact"]:
            continue

        fact_hash = normalized_fact["fact"][:50]  # Берём первые 50 символов для хэша
        if fact_hash in seen_facts:
            logger.warning(f"️ Пропущен дубликат факта: {fact_hash}...")
            continue

        seen_facts.add(fact_hash)
        normalized_facts.append(normalized_fact)

    data["selected_facts"] = normalized_facts

    # 🔥 ИСПРАВЛЕНИЕ №4: Проверка на критически пустые поля
    if not data["central_mystery"] or len(data["central_mystery"]) < 10:
        logger.warning("⚠️ central_mystery слишком короткий или пустой")

    if (
        not data.get("hook_fact", {}).get("fact")
        or len(data.get("hook_fact", {}).get("fact", "")) < 10
    ):
        logger.warning("⚠️ hook_fact слишком короткий или пустой")

    # 🔥 ИСПРАВЛЕНИЕ №5: Финальное логирование результата
    logger.warning("=== [FINAL RESULT] ===")
    logger.warning(f"Story Type: {data.get('story_type')}")
    logger.warning(f"Central Mystery: {data.get('central_mystery', '')[:100]}...")
    logger.warning(f"Hook Fact: {data.get('hook_fact', {}).get('fact', '')[:100]}...")
    logger.warning(f"Selected Facts Count: {len(normalized_facts)}")
    logger.warning(f"Virality Score: {data.get('virality_score')}")
    logger.warning("======================")

    return data


# def generate_story_plan(research_project, provider_name: str) -> dict:
#     """
#     Генерирует сюжетный план на основе данных исследования.
#     Сохраняет все дополнительные поля от ИИ, но жестко гарантирует
#     наличие и корректный тип обязательных полей.
#     """
#     # 1. Получаем промпт из БД
#     try:
#         # Ищем промпт с кодом 'story_planner' (как мы договаривались в админке)
#         prompt_obj = IdeaPrompt.objects.filter(code_name="story_planner", is_active=True).first()

#         # Fallback: если не нашли по code, ищем по code_name (для совместимости)
#         if not prompt_obj:
#             raise StoryPlanValidationError("Активный промпт 'story_planner' не найден в БД.")

#         # Подготавливаем JSON-строку из исследования для вставки в промпт
#         # ✅ ИСПРАВЛЕНИЕ: используем getattr для безопасного получения текста
#         prompt_text_raw = getattr(
#             prompt_obj, "template_content", getattr(prompt_obj, "prompt_text", "")
#         )

#         if not prompt_text_raw:
#             raise StoryPlanValidationError(
#                 "В объекте промпта не найдено поле с текстом (template_content или prompt_text)."
#             )

#         research_json_str = json.dumps(research_project.research_data, ensure_ascii=False, indent=2)
#         prompt_text = prompt_text_raw.replace("{research_json}", research_json_str)

#     except Exception as e:
#         raise StoryPlanValidationError(f"Ошибка подготовки промпта: {e}")

#     # 2. Вызов LLM
#     # Увеличиваем max_tokens, так как story_plan требует детального структурированного вывода
#     raw_response = generate_text(
#         provider_name=provider_name,
#         prompt=prompt_text,
#         max_tokens=3000,
#         temperature=0.7,  # Баланс между креативностью и строгой структурой
#     )

#     # 3. Очистка и парсинг JSON
#     cleaned = raw_response.replace("```json", "").replace("```", "").strip()
#     match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

#     if not match:
#         raise StoryPlanValidationError("AI не вернул JSON объект. Проверьте промпт и ответ модели.")

#     try:
#         data = json.loads(match.group(0))
#     except json.JSONDecodeError as e:
#         raise StoryPlanValidationError(f"AI вернул невалидный JSON: {e}")

#     # 4. БЕЗОПАСНАЯ НОРМАЛИЗАЦИЯ (ГЛАВНАЯ ЗАЩИТА)
#     if not isinstance(data, dict):
#         raise StoryPlanValidationError("Корневой элемент ответа должен быть объектом (dict).")

#     # Гарантируем наличие обязательных полей верхнего уровня.
#     # Неизвестные поля, добавленные ИИ, останутся в словаре нетронутыми!
#     data.setdefault("story_type", "Unknown")
#     data.setdefault("central_mystery", str(data.get("central_mystery", "")))
#     data.setdefault("hook_fact", {"fact": "", "reason": ""})
#     data.setdefault(
#         "story_structure",
#         {"setup": "", "development": [], "reveal": "", "climax": "", "ending": ""},
#     )
#     data.setdefault("selected_facts", [])
#     data.setdefault("discarded_facts", [])

#     # Безопасное приведение типов для ключевых метрик
#     try:
#         data["virality_score"] = int(float(data.get("virality_score", 5) or 5))
#     except (ValueError, TypeError):
#         data["virality_score"] = 5

#     data["narrative_style"] = str(data.get("narrative_style", "DOCUMENTARY")).upper()

#     # Валидация и нормализация списка отобранных фактов
#     if not isinstance(data["selected_facts"], list):
#         data["selected_facts"] = []

#     normalized_facts = []
#     for _, fact in enumerate(data["selected_facts"], start=1):
#         if not isinstance(fact, dict):
#             continue  # Пропускаем битые элементы, а не роняем весь процесс

#         normalized_fact = {
#             "fact": str(fact.get("fact", "")).strip(),
#             "role": str(fact.get("role", "development")).strip(),
#             "selection_reason": str(fact.get("selection_reason", "")).strip(),
#             "scene_concept": str(fact.get("scene_concept", "")).strip(),
#         }

#         try:
#             normalized_fact["visual_priority"] = int(float(fact.get("visual_priority", 5) or 5))
#         except (ValueError, TypeError):
#             normalized_fact["visual_priority"] = 5

#         # Критическая проверка: факт не может быть полностью пустым
#         if normalized_fact["fact"]:
#             normalized_facts.append(normalized_fact)

#     data["selected_facts"] = normalized_facts

#     # Возвращаем итоговый словарь. Он содержит все обязательные поля в правильном формате
#     # + любые дополнительные поля, которые сгенерировал ИИ.
#     return data
