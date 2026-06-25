import json
from django.conf import settings

DOMAINS_FILE = settings.DOMAINS_FILE


def load_domain_presets() -> dict:
    """Загружает пресеты доменов из JSON файла."""
    try:
        with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("presets", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Ошибка загрузки domain presets: {e}")
        return {}


def get_domains_for_preset(preset_key: str) -> list:
    """Возвращает список доменов для конкретного пресета."""
    presets = load_domain_presets()
    if preset_key in presets:
        return presets[preset_key].get("domains", [])
    return []


def get_all_domains() -> list:
    """Возвращает ВСЕ домены из всех пресетов (для полного поиска)."""
    presets = load_domain_presets()
    all_domains = []
    for preset_data in presets.values():
        all_domains.extend(preset_data.get("domains", []))
    return list(set(all_domains))  # Убираем дубликаты


def get_preset_choices() -> list:
    """Возвращает список кортежей (key, label) для формы."""
    presets = load_domain_presets()
    return [(key, data["label"]) for key, data in presets.items()]
