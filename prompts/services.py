from .models import IdeaPrompt, StructurePlanPrompt, ArticlePrompt
import random

import random
from .models import IdeaPrompt


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


def get_structure_prompt():
    """Получает активный промпт для плана."""
    return StructurePlanPrompt.objects.filter(is_active=True).first()


def get_article_prompt():
    """Получает активный промпт для статьи."""
    return ArticlePrompt.objects.filter(is_active=True).first()


def render_idea_prompt(style_code=None, **kwargs):
    template = get_idea_prompt(style_code)
    if not template:
        raise ValueError("No active Idea Prompt found!")
    return template.render(**kwargs)


def render_structure_prompt(**kwargs):
    template = get_structure_prompt()
    if not template:
        raise ValueError("No active Structure Prompt found!")
    return template.render(**kwargs)


def render_article_prompt(**kwargs):
    template = get_article_prompt()
    if not template:
        raise ValueError("No active Article Prompt found!")
    return template.render(**kwargs)
