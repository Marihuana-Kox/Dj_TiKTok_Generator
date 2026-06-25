import json
import re
from ai_inspector.services import generate_text
from prompts.models import ScriptPrompt
from planner.models import StoryPlan


class ShortScriptValidationError(ValueError):
    pass


def get_shorts_director_prompt() -> tuple[str, dict]:
    """Загружает промпт для режиссера сценария. Если нет — останавливает процесс."""
    try:
        # Строго ищем промпт с code="shorts_base"
        prompt_obj = ScriptPrompt.objects.filter(code="shorts_base", is_active=True).first()

        if prompt_obj:
            text = prompt_obj.prompt_text.strip()
            if text:
                return text, prompt_obj.config or {}
    except Exception as e:
        print(f"⚠️ Ошибка загрузки промпта shorts из БД: {e}")

    # ДЕФОЛТНЫЙ ПРОМПТ УБРАН. Процесс останавливается с четкой ошибкой до запроса к AI.
    raise ShortScriptValidationError(
        "Критическая остановка: Промпт 'shorts_base' не найден в базе данных или пуст. "
        "Добавьте его в админ-панель перед запуском генерации."
    )


def generate_short_script_from_plan(story_plan: StoryPlan, provider_name: str):
    """Генерирует финальный сценарий на основе готового StoryPlan."""

    prompt_text, config = get_shorts_director_prompt()

    # Передаем в промпт только релевантную часть story_data, чтобы не перегружать контекст
    plan_context = {
        "title": story_plan.title,
        "narrative_style": story_plan.narrative_style,
        "hook_fact": story_plan.story_data.get("hook_fact", {}),
        "central_mystery": story_plan.story_data.get("central_mystery", ""),
        "story_structure": story_plan.story_data.get("story_structure", {}),
        "selected_facts": story_plan.story_data.get("selected_facts", []),
    }

    story_planner_json = json.dumps(plan_context, ensure_ascii=False, indent=2)
    final_prompt = prompt_text.replace("{story_planner_json}", story_planner_json)

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            temp = 0.7 if attempt == 1 else 0.2
            raw_response = generate_text(
                provider_name=provider_name, prompt=final_prompt, max_tokens=3000, temperature=temp
            )
            return parse_and_validate_short_script(raw_response, config)
        except ShortScriptValidationError as e:
            if attempt == 1:
                print(f"⚠️ Попытка 1 провалилась: {e}. Пробуем строгий режим...")
                final_prompt = f"КРИТИЧЕСКАЯ ОШИБКА: Ты нарушил формат. Верни СТРОГО валидный JSON по схеме. Данные плана: {story_planner_json}"
                continue
            raise e


def parse_and_validate_short_script(raw_text: str, config: dict):
    if not raw_text:
        raise ShortScriptValidationError("AI вернул пустой ответ.")

    cleaned = raw_text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ShortScriptValidationError("В ответе AI нет JSON объекта.")

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ShortScriptValidationError(f"AI вернул невалидный JSON: {exc}")

    if not isinstance(data, dict):
        raise ShortScriptValidationError("JSON должен быть объектом.")

    # --- ВАЛИДАЦИЯ НОВЫХ МЕТАДАННЫХ ---
    short_title = str(data.get("short_title", "")).strip()
    if not short_title or len(short_title) > 80:
        raise ShortScriptValidationError(
            "Поле 'short_title' обязательно и должно быть коротким (до 80 символов)."
        )

    hashtags = data.get("hashtags", [])
    if not isinstance(hashtags, list) or len(hashtags) != 5:
        raise ShortScriptValidationError(
            "Поле 'hashtags' должно быть списком ровно из 5 элементов."
        )
    hashtags = [str(tag).strip() for tag in hashtags]

    description = str(data.get("description", "")).strip()
    if not description:
        raise ShortScriptValidationError("Поле 'description' обязательно.")

    # --- ВАЛИДАЦИЯ ОСНОВНЫХ ПОЛЕЙ ---
    style = str(data.get("style", "SHOCK")).upper().strip()
    if style not in {"DOCUMENTARY", "SHOCK", "THEORY"}:
        style = "SHOCK"

    hook = str(data.get("hook", "")).strip()
    voiceover = str(data.get("voiceover", "")).strip()
    scenes = data.get("scenes")

    if not hook or not voiceover:
        raise ShortScriptValidationError("Поля hook или voiceover пусты.")

    # Используем конфиг из БД, fallback на 7-10 сцен согласно твоему промпту
    min_scenes = config.get("min_scenes", 7)
    max_scenes = config.get("max_scenes", 10)

    if not isinstance(scenes, list) or not (min_scenes <= len(scenes) <= max_scenes):
        raise ShortScriptValidationError(
            f"Поле scenes должно содержать {min_scenes}-{max_scenes} сцен."
        )

    normalized_scenes = []
    total_duration = 0
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue

        text = str(scene.get("text", "")).strip()
        image_prompt = str(scene.get("image_prompt", "")).strip()

        # Новые поля из твоего промпта
        scene_number = int(scene.get("scene_number", index))
        role = str(scene.get("role", "development")).strip()
        camera_motion = str(scene.get("camera_motion", "static")).strip()
        transition = str(scene.get("transition", "fade")).strip()
        emotion = str(scene.get("emotion", "mystery")).strip()

        try:
            duration = int(float(scene.get("duration", 8) or 8))
            visual_priority = int(float(scene.get("visual_priority", 5) or 5))
        except (TypeError, ValueError):
            duration = 8
            visual_priority = 5

        # Ограничители из промпта (8-12 секунд, приоритет 1-10)
        duration = max(8, min(duration, 12))
        visual_priority = max(1, min(visual_priority, 10))
        total_duration += duration

        if not text or not image_prompt:
            raise ShortScriptValidationError(f"Сцена {index} пустая (нет text или image_prompt).")

        normalized_scenes.append(
            {
                "scene_number": scene_number,
                "role": role,
                "text": text,
                "image_prompt": image_prompt,
                "duration": duration,
                "camera_motion": camera_motion,
                "transition": transition,
                "emotion": emotion,
                "visual_priority": visual_priority,
            }
        )

    return {
        "short_title": short_title,
        "hashtags": hashtags,
        "description": description,
        "style": style,
        "hook": hook,
        "voiceover": voiceover,
        "scenes": normalized_scenes,
    }
