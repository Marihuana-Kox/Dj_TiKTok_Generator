import json
import re

from ai_inspector.services import generate_text


SHORT_SCRIPT_PROMPT = """
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

ФОРМАТ ОТВЕТА (строго JSON):
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
- каждый image_prompt должен быть кинематографичным
- image_prompt всегда пиши на английском языке
- стиль должен влиять на текст и визуал
- никаких объяснений, только JSON

ТЕМА:
__TOPIC__
""".strip()


class ShortScriptValidationError(ValueError):
    pass


def build_short_script_prompt(topic):
    return SHORT_SCRIPT_PROMPT.replace("__TOPIC__", topic.strip())


def parse_short_script_json(raw_text):
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

    return validate_short_script_data(data)


def validate_short_script_data(data):
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
    if not isinstance(scenes, list) or not 4 <= len(scenes) <= 7:
        raise ShortScriptValidationError("Поле scenes должно содержать 4-7 сцен.")

    normalized_scenes = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ShortScriptValidationError(f"Сцена {index} должна быть объектом.")

        text = str(scene.get("text", "")).strip()
        image_prompt = str(scene.get("image_prompt", "")).strip()
        duration = scene.get("duration", 3)

        try:
            duration = int(duration)
        except (TypeError, ValueError) as exc:
            raise ShortScriptValidationError(f"duration в сцене {index} должен быть числом.") from exc

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


def generate_short_script(topic, provider_name):
    prompt = build_short_script_prompt(topic)
    raw_response = generate_text(provider_name, prompt, max_tokens=2200, temperature=0.8)
    return parse_short_script_json(raw_response)
