from django.core.exceptions import ObjectDoesNotExist
from .models import IdeaPrompt, SystemInstruction, ArticlePrompt
import random


def get_random_idea_prompt():
    """Получает случайный активный промпт для идеи."""
    return IdeaPrompt.objects.filter(is_active=True).order_by("?").first()


def get_idea_prompt(style_code=None):
    """
    Получает активный промпт.
    Если style_code='random', выбирает случайный активный промпт.
    """
    qs = IdeaPrompt.objects.filter(is_active=True)

    if not qs.exists():
        return None

    if style_code == 'random':
        # Выбираем случайный промпт из всех активных
        return random.choice(list(qs))

    # Если указан конкретный стиль
    if style_code:
        qs = qs.filter(code_name=style_code)
        if qs.exists():
            # Если промптов этого стиля несколько, тоже берем случайный для разнообразия
            return random.choice(list(qs))

    # Фоллбэк: если стиль не найден, берем любой активный
    return qs.first()


def get_system_instruction():
    """Получает активную системную инструкцию."""
    return SystemInstruction.objects.filter(is_active=True).first()


def get_article_prompt():
    """Получает активный промпт для статьи."""
    return ArticlePrompt.objects.filter(is_active=True).first()


def render_idea_prompt(style_code=None, **kwargs):
    template = get_idea_prompt(style_code)
    if not template:
        raise ValueError("No active Idea Prompt found!")
    return template.render(**kwargs)


def render_system_instruction(**kwargs):
    template = get_system_instruction()
    if not template:
        raise ValueError("No active System Instruction found!")
    return template.render(**kwargs)


def render_article_prompt(**kwargs):
    template = get_article_prompt()
    if not template:
        raise ValueError("No active Article Prompt found!")
    return template.render(**kwargs)


def get_system_instruction(code_name, context_data):
    """
    Получает инструкцию из БД по коду и рендерит её данными из context_data.

    Args:
        code_name (str): Поле 'name' модели (например, 'translation_strict')
        context_data (dict): Словарь переменных для подстановки (например, {'target_lang': 'Русский', 'article_content': '...'})

    Returns:
        str: Готовый промпт
    """
    try:
        instruction = SystemInstruction.objects.get(
            code_name=code_name, is_active=True)
    except ObjectDoesNotExist:
        raise ValueError(
            f"Системная инструкция '{code_name}' не найдена в базе данных!")

    # Рендерим шаблон, подставляя переменные
    try:
        rendered_text = instruction.template_content.format(**context_data)
        return rendered_text
    except KeyError as e:
        raise ValueError(
            f"В тексте инструкции есть переменная {e}, но она не передана в context_data!")
