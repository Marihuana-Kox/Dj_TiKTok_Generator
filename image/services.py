import os
import json
from openai import OpenAI  # Или Gemini
from config.models import SystemConfig


def generate_scene_prompts(project, num_scenes: int = None, aspect_ratio: str = '9:16'):
    """
    Генерирует промпты на основе текста статьи.
    """
    script = project.script_data
    if not script:
        raise Exception("Нет текста статьи для генерации промптов!")

    config = SystemConfig.get_config()

    # Используем тот же ключ, что и для статьи
    client = OpenAI(api_key=config.openai_key)
    model = config.default_article_model  # Или отдельная модель для картинок

    # Если количество не указано, предлагаем AI решить самому (обычно 4-6)
    count_instr = f"Generate exactly {num_scenes} scenes." if num_scenes else "Break the story into logical visual scenes (usually 4-6)."

    system_prompt = f"""
    You are an expert AI Art Director for TikTok videos.
    Task: Break the following script into visual scenes and write detailed image prompts for Flux/Midjourney.
    
    Constraints:
    - Aspect Ratio: {aspect_ratio}
    - Style: Photorealistic, cinematic lighting, historical accuracy mixed with mystery.
    - Output: JSON list of strings.
    """

    user_prompt = f"""
    Script:
    {script.script_en}

    {count_instr}
    
    Return JSON: {{ "prompts": ["prompt 1", "prompt 2", ...] }}
    """

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_prompt}],
        response_format={"type": "json_object"},
        temperature=0.7
    )

    data = json.loads(response.choices[0].message.content)
    return data.get('prompts', [])
