import json
import re
import traceback
from datetime import timedelta
from django.utils import timezone

from prompts.models import IdeaPrompt
from topics.helpers.blacklist import get_banned_domains
from topics.helpers.search_templates import generate_search_queries
from .models import VideoProject
from ai_inspector.services import generate_text, search_with_tavily
from prompts.services import get_random_idea_prompt

# ПРОВЕРКА ИМПОРТА НА УРОВНЕ МОДУЛЯ
try:
    from prompts.services import render_idea_prompt

    DEFAULT_PROMPTS_ENABLED = True
except ImportError:
    DEFAULT_PROMPTS_ENABLED = False
    print("⚠️ Prompts app not found. Using fallback logic.")


class ResearchValidationError(ValueError):
    pass


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
        s = re.sub(r"^```.*?\n", "", s, flags=re.DOTALL)
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]

    s = s.strip()

    # 2. Список префиксов, которые часто лепит AI
    prefixes = [
        "the translated title is:",
        "the translated title is:",
        "translation:",
        "english:",
        "here is the english translation:",
        "title:",
        "angle_en:",
        "the title in english is:",
        "translated as:",
        "i suggest:",
    ]

    s_lower = s.lower()
    for p in prefixes:
        if s_lower.startswith(p):
            s = s[len(p) :].strip()
            break

    # 3. Удаляем постфиксы и комментарии внутри строки (часто бывает после двоеточия или слова However)
    stop_words = ["However", "Note that", "It seems", "But", "Also,", "Explanation:", "Comment:"]
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


def generate_unique_ideas(
    provider_name="huggingface",
    count=3,
    topic="История",
    focus_topics=None,
    idea_style="facts",
    refresh_old=False,
    refresh_days=None,
    allow_duplicates=False,
    no_duplicate_days=None,
    callback=None,
):
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
            topic=f"Генерация #{i + 1}...", angle=f"Ожидание AI...", notes="", status="pending"
        )
        idea_objects.append(obj)
        if callback:
            callback(
                current=i + 1,
                total=count,
                step="create_queue",
                message=f"Queue #{i + 1}",
                idea_id=obj.id,
            )

    # --- 1. Сбор контекста ---
    banned_list = []
    if not allow_duplicates and no_duplicate_days:
        cutoff_date = timezone.now() - timedelta(days=no_duplicate_days)
        recent_ideas = VideoProject.objects.filter(created_at__gte=cutoff_date)
        for idea in recent_ideas:
            banned_list.append(f"- {idea.topic}: {idea.angle}")
    else:
        recent_ideas = VideoProject.objects.order_by("-created_at")[:50]
        for idea in recent_ideas:
            banned_list.append(f"- {idea.topic}: {idea.angle} (OK)")

    banned_context = "\n".join(banned_list) if banned_list else "No restrictions."

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
            topics_to_process = [f"Idea #{i + 1}" for i in range(count)]

        for index, idea_obj in enumerate(idea_objects):
            current_num = index + 1
            current_topic_string = topics_to_process[index]

            if callback:
                callback(
                    current=current_num,
                    total=count,
                    step="generating",
                    message=f"Processing: {current_topic_string}...",
                    idea_id=idea_obj.id,
                )

            system_prompt = ""

            # Попытка получить промпт из БД
            if prompts_enabled:
                try:
                    if idea_style == "random":
                        obj = get_random_idea_prompt()  # 1. Добавили скобки () для вызова
                        if obj:  # 2. Проверка: если промпт найден
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
                        language="English",
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
                response_text = generate_text(provider_name, system_prompt, max_tokens=1000)

                clean_json = response_text.strip()

                # Очистка от маркдаун блоков
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                if clean_json.startswith("[") and clean_json.endswith("]"):
                    clean_json = clean_json[1:-1]

                # Попытка найти JSON внутри текста, если модель добавила пояснения
                match = re.search(r"\{.*\}", clean_json, re.DOTALL)
                if match:
                    clean_json = match.group()

                data = json.loads(clean_json)

                # --- ИЗВЛЕЧЕНИЕ И ОЧИСТКА ДАННЫХ ---

                # 1. Тема (Рубрика)
                category_ru = clean_ai_string(data.get("topic_ru", current_topic_string))
                category_en = clean_ai_string(data.get("topic_en", category_ru))

                # 2. Заголовок (Angle)
                raw_angle_ru = data.get("angle_ru", "")
                raw_angle_en = data.get("angle_en", "")

                final_angle_ru = clean_ai_string(raw_angle_ru)
                final_angle_en = clean_ai_string(raw_angle_en)

                # Фоллбэк: если модель не вернула заголовки, используем summary
                if not final_angle_ru and not final_angle_en:
                    summary = clean_ai_string(data.get("summary", "New Story"))
                    final_angle_ru = f"{category_ru}: {summary[:50]}"

                # Фоллбэк: если нет английского перевода, делаем микро-запрос
                if final_angle_ru and not final_angle_en:
                    try:
                        print(f"   -> Переводим заголовок на EN: {final_angle_ru[:30]}...")
                        trans_prompt = f"Translate this title to English ONLY. No extra text: '{final_angle_ru}'"
                        final_angle_en = clean_ai_string(
                            generate_text(provider_name, trans_prompt, max_tokens=60)
                        )
                    except Exception as e:
                        print(f"   ⚠️ Ошибка перевода: {e}")
                        final_angle_en = final_angle_ru  # Оставляем русский как крайний вариант

                # Фоллбэк: если нет русского (редко), переводим с английского
                if final_angle_en and not final_angle_ru:
                    try:
                        trans_prompt = f"Translate this title to Russian ONLY. No extra text: '{final_angle_en}'"
                        final_angle_ru = clean_ai_string(
                            generate_text(provider_name, trans_prompt, max_tokens=60)
                        )
                    except:
                        final_angle_ru = final_angle_en

                # 3. Notes (Факты и Вопросы + СПЕЦ. МЕТКА ДЛЯ AI)
                ai_summary = clean_ai_string(data.get("summary", ""))
                facts_list = data.get("facts", [])
                questions_list = data.get("questions", [])

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
                idea_obj.status = "new"
                # Убедись, что имя поля (prompt_code) совпадает с тем, что ты создал в модели
                if hasattr(idea_obj, "idea_style"):
                    print(f"🔍 DEBUG: Сохраняем в prompt_code значение: '{idea_style}'")
                    idea_obj.idea_style = idea_style
                idea_obj.save()

                saved_count += 1
                print(
                    f"✅ Создана идея: [{idea_obj.topic}] -> {idea_obj.angle} | EN: {final_angle_en}"
                )

                if callback:
                    callback(
                        current=current_num,
                        total=count,
                        step="saved",
                        message=f"Готово: {idea_obj.angle}",
                        idea_id=idea_obj.id,
                    )

            except Exception as e:
                err_msg = str(e)
                print(f"❌ Error for '{current_topic_string}': {err_msg}")
                if callback:
                    callback(
                        current=current_num,
                        total=count,
                        step="error",
                        message=f"Error: {err_msg[:30]}",
                        idea_id=idea_obj.id,
                    )

                idea_obj.topic = "Ошибка генерации"
                idea_obj.angle = current_topic_string
                idea_obj.notes = f"Generation failed: {err_msg}"
                idea_obj.status = "rejected"  # Исправлено на стандартный статус
                idea_obj.save()

        print(f"🎉 Итог: успешно создано {saved_count} идей.")
        return saved_count

    except Exception as e:
        print(f"❌ Критическая ошибка в generate_unique_ideas: {e}")
        raise


def generate_research_data(
    topic: str,
    provider_name: str,
    style: str,
    focus_notes: str = "",
    use_web_search: bool = True,
    search_provider: str = "tavily_search",
    include_domains: list = None,
    exclude_domains: list = None,
    search_category: str = "general",
) -> dict:
    """Acts strictly as a raw research engine collector for the downstream Planner."""
    import json
    import re

    search_context = ""

    # ==========================================
    # ЭТАП 1: ПОИСК В ИНТЕРНЕТЕ (Tavily)
    # ==========================================
    if use_web_search:
        try:
            print(
                f"\n{'=' * 80}\n🔍 [RESEARCH] Smart search for topic: '{topic}' | Category: {search_category}\n{'=' * 80}"
            )

            search_queries = generate_search_queries(
                topic=topic,
                category=search_category,
                focus_notes=focus_notes,
                count=6,
                randomize=True,
            )

            all_results = []
            all_images = []
            seen_urls = set()
            seen_img_urls = set()
            summaries = []

            for i, query_template in enumerate(search_queries, 1):
                try:
                    search_query = str(query_template)
                    if focus_notes:
                        search_query += f". {focus_notes.strip()}"

                    if len(search_query) > 400:
                        search_query = search_query[:400].rsplit(" ", 1)[0]

                    print(f"🔎 [{i}/{len(search_queries)}] Tavily: '{search_query}'")

                    search_data = search_with_tavily(
                        query=search_query,
                        provider_name=search_provider,
                        max_results=20,
                        include_images=True,
                        include_domains=include_domains,
                        exclude_domains=get_banned_domains(),
                    )

                    for r in search_data.get("results", []):
                        url = r.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(r)

                    if search_data.get("answer"):
                        summaries.append(search_data["answer"].strip())

                    for img in search_data.get("images", []):
                        img_url = img.get("url", "") if isinstance(img, dict) else str(img)
                        if img_url and img_url not in seen_img_urls:
                            seen_img_urls.add(img_url)
                            all_images.append(img)

                except Exception as e:
                    print(f"   ⚠️ Request error #{i}: {e}")
                    continue

            # Формирование и обрезка контекста ПОСЛЕ завершения всех запросов
            if not all_results:
                search_context = "Web search returned no results. Use internal knowledge."
            else:
                MAX_SOURCE_LENGTH = 800
                MAX_TOTAL_SOURCES = 15
                MAX_CONTEXT_LENGTH = 15000

                sorted_results = sorted(all_results, key=lambda x: x.get("score", 0), reverse=True)
                top_results = sorted_results[:MAX_TOTAL_SOURCES]

                print(
                    f"📊 [RESEARCH] Формируем контекст: ТОП-{len(top_results)} из {len(all_results)} источников"
                )

                ctx_blocks = []

                if summaries:
                    # Берем самое релевантное саммари
                    ctx_blocks.append(f"=== TAVILY SUMMARY ===\n{summaries[0][:1000]}\n")

                ctx_blocks.append("=== COMBINED RESEARCH RESULTS ===")
                for idx, r in enumerate(top_results, 1):
                    title = str(r.get("title", ""))[:200]
                    content = str(r.get("content", ""))[:MAX_SOURCE_LENGTH]
                    ctx_blocks.append(
                        f"--- SOURCE {idx} (score: {r.get('score', 0)}) ---\n"
                        f"Title: {title}\n"
                        f"URL: {r.get('url', '')}\n"
                        f"Content: {content}\n"
                    )

                if all_images:
                    ctx_blocks.append(f"\n=== COLLECTED IMAGES ({len(all_images)} found) ===")
                    for idx, img in enumerate(
                        all_images[:20], 1
                    ):  # Лимитируем список картинок для LLM
                        if isinstance(img, dict):
                            ctx_blocks.append(
                                f"[{idx}] URL: {img.get('url', '')}\nDescription: {img.get('description', '')}\n"
                            )
                        else:
                            ctx_blocks.append(f"[{idx}] URL: {str(img)}\n")
                    ctx_blocks.append("=== END OF COLLECTED IMAGES ===")

                search_context = "\n".join(ctx_blocks)

                if len(search_context) > MAX_CONTEXT_LENGTH:
                    print(
                        f"⚠️ [RESEARCH] Контекст превышает лимит ({len(search_context)} символов). Обрезка до {MAX_CONTEXT_LENGTH}..."
                    )
                    search_context = (
                        search_context[:MAX_CONTEXT_LENGTH]
                        + "\n\n[...context truncated due to length...]"
                    )

                print(f"✅ Context packed: {len(search_context)} characters.")

        except Exception as e:
            print(f"⚠️ Search failed: {e}. Going internal.")
            search_context = "Web search unavailable. Use internal knowledge."

    # ==========================================
    # ЭТАП 2: ГЕНЕРАЦИЯ ИССЛЕДОВАНИЯ ЧЕРЕЗ LLM
    # ==========================================
    try:
        prompt_filter = {"is_active": True}
        if style == "random":
            prompt_obj = IdeaPrompt.objects.filter(**prompt_filter).order_by("?").first()
        else:
            prompt_obj = IdeaPrompt.objects.filter(code_name=style, **prompt_filter).first()

        if not prompt_obj:
            raise ResearchValidationError("Active prompt template not found in DB.")

        prompt_text = prompt_obj.template_content.replace("{topic}", topic.strip())
        notes = focus_notes.strip() if focus_notes else "None."
        prompt_text = prompt_text.replace("{focus_notes}", notes)

        if "{search_results}" in prompt_text:
            prompt_text = prompt_text.replace("{search_results}", search_context)
        else:
            prompt_text += f"\n\n=== WEB SEARCH RESULTS ===\n{search_context}"

    except Exception as e:
        raise ResearchValidationError(f"Prompt build error: {e}")

    raw_response = generate_text(
        provider_name=provider_name,
        prompt=prompt_text,
        max_tokens=4000,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    cleaned = raw_response.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ResearchValidationError("LLM failed to return a valid JSON object.")

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ResearchValidationError(f"JSON Syntax Error: {e}")

    if data.get("status") == "INSUFFICIENT_RESEARCH":
        reason = (
            data.get("reason")
            or data.get("message")
            or "LLM filtered out all facts as common knowledge/low virality."
        )
        raise ResearchValidationError(f"Insufficient historical friction metrics. Reason: {reason}")

    if "facts" not in data or not isinstance(data["facts"], list):
        raise ResearchValidationError("Root key 'facts' must be a valid array.")

    normalized_facts = []
    for index, fact in enumerate(data["facts"], start=1):
        if not isinstance(fact, dict):
            raise ResearchValidationError(f"Fact block #{index} must be an object.")

        fact_text = str(fact.get("fact", "")).strip()
        if not fact_text:
            raise ResearchValidationError(f"Fact text missing in block #{index}.")

        normalized_facts.append(
            {
                "fact": fact_text,
                "detailed_intel": str(fact.get("detailed_intel", "")).strip(),
                "primary_emotional_trigger": str(fact.get("primary_emotional_trigger", ""))
                .split("|")[0]
                .strip(),
                "why_it_matters": str(fact.get("why_it_matters", "")).strip(),
                "visual_description": str(fact.get("visual_description", "")).strip(),
                "metrics": {
                    "surprise": int(float(fact.get("metrics", {}).get("surprise", 0) or 0)),
                    "conflict": int(float(fact.get("metrics", {}).get("conflict", 0) or 0)),
                    "reinterpretation": int(
                        float(fact.get("metrics", {}).get("reinterpretation", 0) or 0)
                    ),
                },
                "virality_score": int(float(fact.get("virality_score", 0) or 0)),
                "evidence_level": str(fact.get("evidence_level", "confirmed")).strip(),
                "source_url": str(fact.get("source_url", "")).strip(),
            }
        )

    data["facts"] = normalized_facts

    scores = [f["virality_score"] for f in normalized_facts]
    data["overall_emotional_score"] = round(sum(scores) / len(scores)) if scores else 0

    data.setdefault("status", "SUCCESS")
    data.setdefault("topic", topic.strip())
    data.setdefault("discarded_facts", [])

    valid_images = []
    for img in data.get("selected_images", []):
        if isinstance(img, dict) and img.get("image_url"):
            valid_images.append(
                {
                    "image_url": str(img.get("image_url", "")).strip(),
                    "image_reason": str(img.get("image_reason", "")).strip(),
                    "associated_fact": str(img.get("associated_fact", "")).strip(),
                }
            )
    data["selected_images"] = valid_images

    return data
