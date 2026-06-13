import json
import re
from ai_inspector.services import generate_text
from prompts.models import ScriptPrompt


class ShortScriptValidationError(ValueError):
    pass


# Дефолтный промпт (fallback)
FALLBACK_PROMPT = """
Ты - режиссёр TikTok исторических видео.
Твоя задача:
1. Определи лучший стиль: DOCUMENTARY / SHOCK / THEORY
2. Создай сценарий для ролика

СТИЛИ:
- DOCUMENTARY: факты, нейтрально, как Netflix
- SHOCK: вирусный, интригующий, сильный хук
- THEORY: гипотезы, загадки, альтернативные версии

ЛОГИКА ВЫБОРА СТИЛЯ:
- SHOCK выбирай, если есть загадка, древние артефакты, необъяснимое, тайна, скрытые факты
- DOCUMENTARY выбирай, если тема про исторические события, войны, личности, и нужна точность
- THEORY выбирай, если нет точного ответа, тема про археологию, космос, древние цивилизации или альтернативные версии

ФОРМАТ ОТВЕТА (строго JSON, без markdown, без пояснений):
{
 "style": "",
 "hook": "",
 "voiceover": "",
 "scenes": [
  {
   "text": "",
   "image_prompt": "",
   "duration": 3
  }
 ]
}

ПРАВИЛА:
- hook: максимум 2 предложения
- voiceover: единый текст для озвучки
- scenes: 4-7 сцен
- каждый image_prompt должен быть кинематографичным и на английском языке
- стиль должен влиять на текст и визуал
- НИКАКИХ объяснений, только валидный JSON

ТЕМА:
{TOPIC}
""".strip()


def get_script_prompt(style_hint: str = None) -> tuple[str, dict]:
    """Загружает промпт из БД. Если нет → возвращает fallback."""
    try:
        qs = ScriptPrompt.objects.filter(is_active=True)
        if style_hint:
            qs = qs.filter(code=style_hint.upper())

        prompt_obj = qs.first()
        if prompt_obj and prompt_obj.prompt_text.strip():
            return prompt_obj.prompt_text.strip(), prompt_obj.config or {}
    except Exception as e:
        print(f"⚠️ Ошибка загрузки промпта из БД: {e}")

    return FALLBACK_PROMPT, {"min_scenes": 4, "max_scenes": 7, "lang": "en"}


def build_short_script_prompt(topic: str, style_hint: str = None) -> tuple[str, dict]:
    prompt_text, config = get_script_prompt(style_hint)
    return prompt_text.replace("{TOPIC}", topic.strip()), config


def validate_short_script_data(data: dict, config: dict):
    """Валидация с учётом настроек из БД."""
    if not isinstance(data, dict):
        raise ShortScriptValidationError("JSON должен быть объектом.")

    style = str(data.get("style", "")).upper().strip()
    if style not in {"DOCUMENTARY", "SHOCK", "THEORY"}:
        raise ShortScriptValidationError("Поле style должно быть DOCUMENTARY, SHOCK или THEORY.")

    hook = str(data.get("hook", "")).strip()
    voiceover = str(data.get("voiceover", "")).strip()
    scenes = data.get("scenes")

    if not hook:
        raise ShortScriptValidationError("Поле hook пустое.")
    if not voiceover:
        raise ShortScriptValidationError("Поле voiceover пустое.")

    # ✅ Используем конфиг из БД вместо хардкода
    min_scenes = config.get("min_scenes", 4)
    max_scenes = config.get("max_scenes", 7)

    if not isinstance(scenes, list) or not (min_scenes <= len(scenes) <= max_scenes):
        raise ShortScriptValidationError(
            f"Поле scenes должно содержать {min_scenes}-{max_scenes} сцен."
        )

    normalized_scenes = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ShortScriptValidationError(f"Сцена {index} должна быть объектом.")

        text = str(scene.get("text", "")).strip()
        image_prompt = str(scene.get("image_prompt", "")).strip()
        duration = scene.get("duration", 3)

        try:
            duration = int(duration)
        except (TypeError, ValueError):
            raise ShortScriptValidationError(f"duration в сцене {index} должен быть числом.")

        if not text:
            raise ShortScriptValidationError(f"Поле text пустое в сцене {index}.")
        if not image_prompt:
            raise ShortScriptValidationError(f"Поле image_prompt пустое в сцене {index}.")

        normalized_scenes.append(
            {
                "text": text,
                "image_prompt": image_prompt,
                "duration": max(1, min(duration, 15)),
            }
        )

    return {
        "style": style,
        "hook": hook,
        "voiceover": voiceover,
        "scenes": normalized_scenes,
    }


def parse_short_script_json(raw_text: str, config: dict):
    if not raw_text:
        raise ShortScriptValidationError("AI вернул пустой ответ.")

    cleaned = raw_text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ShortScriptValidationError("В ответе AI нет JSON объекта.")

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ShortScriptValidationError(f"AI вернул невалидный JSON: {exc}") from exc

    return validate_short_script_data(data, config)


def generate_short_script(topic: str, provider_name: str, style_hint: str = None):
    """Генерация с retry-логикой и поддержкой конфига из БД."""
    prompt, config = build_short_script_prompt(topic, style_hint)
    max_attempts = 2

    for attempt in range(1, max_attempts + 1):
        try:
            # На первой попытке temperature=0.8 (креатив), на второй=0.2 (строгость)
            temp = 0.8 if attempt == 1 else 0.2
            raw_response = generate_text(provider_name, prompt, max_tokens=2200, temperature=temp)
            return parse_short_script_json(raw_response, config)

        except ShortScriptValidationError as e:
            if attempt == 1:
                print(f"⚠️ Попытка 1 провалилась: {e}. Пробуем строгий режим...")
                # Меняем промпт на жёсткий retry
                prompt = f"Ты сломал формат JSON. Верни СТРОГО валидный JSON по схеме. Тема: {topic}. Никакого текста кроме JSON."
                continue
            raise e  # Если и вторая упала → пробрасываем ошибку в view
