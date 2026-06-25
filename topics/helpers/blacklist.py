import json
from django.conf import settings

# 🔥 УКАЖИ ПРАВИЛЬНЫЙ ПУТЬ К ТВОЕМУ ФАЙЛУ
# Если файл лежит в корне проекта (рядом с manage.py):
BLACKLIST_FILE = settings.BLACK_LIST_SITES

# Если файл лежит вообще вне проекта, укажи абсолютный путь:
# BLACKLIST_FILE = Path("/путь/к/твоей/папке/black_list.json")


def get_banned_domains() -> list:
    """Загружает список запрещенных доменов из отдельного JSON файла."""
    try:
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Поддержка разных форматов JSON: просто список или словарь
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("banned_domains", data.get("exclude_domains", []))
        return []

    except FileNotFoundError:
        print(f"⚠️ Файл black_list.json не найден по пути: {BLACKLIST_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"️ Ошибка парсинга black_list.json: {e}")
        return []
