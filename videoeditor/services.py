import urllib.parse

from .models import ProjectVideoRelease


def sanitize_media_path(path_unquote):
    """
    Универсальная затычка: переводит кириллицу в путях в транслит,
    заменяет пробелы на подчеркивания, делая путь безопасным для MoviePy.
    """
    if not path_unquote:
        return path_unquote

    # Словарь перевода основных русских букв
    cyrillic_translit = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "А": "A",
        "Б": "B",
        "В": "V",
        "Г": "G",
        "Д": "D",
        "Е": "E",
        "Ё": "Yo",
        "Ж": "Zh",
        "З": "Z",
        "И": "I",
        "Й": "Y",
        "К": "K",
        "Л": "L",
        "М": "M",
        "Н": "N",
        "О": "O",
        "П": "P",
        "Р": "R",
        "С": "S",
        "Т": "T",
        "У": "U",
        "Ф": "F",
        "Х": "Kh",
        "Ц": "Ts",
        "Ч": "Ch",
        "Ш": "Sh",
        "Щ": "Shch",
        "Ъ": "",
        "Ы": "Y",
        "Ь": "",
        "Э": "E",
        "Ю": "Yu",
        "Я": "Ya",
    }

    # Сначала меняем пробелы на нижнее подчеркивание
    path_str = urllib.parse.unquote(str(path_unquote))
    fixed_str = path_str.replace(" ", "_")

    # Посимвольно заменяем кириллицу
    processed_chars = [cyrillic_translit.get(char, char) for char in fixed_str]
    return "".join(processed_chars)


def debug_project_config_state(project_id, final_timeline_data):
    """
    Дамп всех сгенерированных конфигураций видео из массива истории `pj_config`.
    """
    try:
        release_info = ProjectVideoRelease.objects.filter(project_id=project_id).first()

        print("\n" + "═" * 80)
        print(
            f"📜 ИСТОРИЯ СГЕНЕРИРОВАННЫХ СБОРОК ИЗ ТАБЛИЦЫ БД (pj_config) ПРОЕКТА ID: {project_id}"
        )
        print("═" * 80)

        if not release_info:
            print("⚠️ Запись ProjectVideoRelease для этого проекта отсутствует в БД.")
            print("═" * 80 + "\n")
            return

        history_configs = release_info.pj_config or []

        print(f"📊 Всего успешных генераций в истории: {len(history_configs)}")
        print("═" * 80)

        # Перебираем каждую сохраненную сборку в pj_config
        for c_idx, config_entry in enumerate(history_configs):
            config_id = config_entry.get("config_id", "N/A")
            updated_at = config_entry.get("updated_at", "N/A")
            scenes_count = config_entry.get("scenes_count", 0)
            timeline_state = config_entry.get("timeline_state", [])

            print(f"🚀 СБОРКА #{config_id} | 📅 Дата: {updated_at} | 🎬 Сцен: {scenes_count}")
            print("─" * 80)

            # Выводим сцены, которые зафиксировались внутри этой генерации
            for s_idx, scene in enumerate(timeline_state):
                meta = scene.get("meta_settings", {})
                order = scene.get("order", s_idx + 1)
                img_name = meta.get("image_name", "Нет картинки")
                duration = meta.get("duration", "5.0")
                v_effect = meta.get("video_effects", "none")
                v_filter = meta.get("filter", "none")
                transition = meta.get("transition", "none")

                print(
                    f"   [Сцена {s_idx + 1}] Порядок: {order} | Кадр: {img_name.split('/')[-1]} | ⏱️ {duration}с | ✨ Эффект: {v_effect}"
                )

            print("═" * 80)

        print(f"📊 ТЕКУЩИЙ СТАТУС В ШАБЛОНЕ (timeline_data): {len(final_timeline_data)} элементов.")
        print("═" * 80 + "\n")

    except Exception as e:
        print(f"❌ Ошибка при чтении истории генераций ролика: {str(e)}")

    # """
    # Выводит в консоль терминала точное состояние конфигураций из базы данных
    # и сравнивает его с тем, что ушло в HTML-шаблон.
    # """
    # try:
    #     release_info = ProjectVideoRelease.objects.filter(project_id=project_id).first()

    #     print("\n" + "=" * 60)
    #     print(f"🔍 ДИАГНОСТИКА КОНФИГУРАЦИИ ПРОЕКТА (ID: {project_id})")
    #     print("=" * 60)

    #     if not release_info:
    #         print("⚠️ Запись ProjectVideoRelease для этого проекта ещё не создана в БД.")
    #         print("=" * 60 + "\n")
    #         return

    #     # 1. Данные напрямую из полей JSON в базе данных
    #     history_cfg = release_info.pj_config or []
    #     current_cfg = release_info.pj_current_config or []

    #     print(f"🔹 [БАЗА ДАННЫХ] Элементов в истории (pj_config): {len(history_cfg)}")
    #     print(
    #         f"🔹 [БАЗА ДАННЫХ] Элементов в текущем черновике (pj_current_config): {len(current_cfg)}"
    #     )

    #     if len(current_cfg) > 0:
    #         print("   👉 Список картинок в pj_current_config:")
    #         for idx, item in enumerate(current_cfg):
    #             meta = item.get("meta_settings", {})
    #             img_name = meta.get("image_name", "НЕТ КАРТИНКИ")
    #             print(f"      {idx + 1}. Порядок: {item.get('order')} | Файл: {img_name}")
    #     else:
    #         print("   👉 Текущий черновик в БД пуст (первый запуск).")

    #     print("-" * 60)

    #     # 2. Данные, собранные для вывода в HTML-шаблон
    #     print(
    #         f"🎬 [HTML-ШАБЛОН] Получил для отрисовки (timeline_data): {len(final_timeline_data)} сюжетов."
    #     )
    #     if len(final_timeline_data) > 0:
    #         for idx, item in enumerate(final_timeline_data):
    #             order = item.get("order")
    #             track = item.get("track")
    #             prompt = item.get("prompt")

    #             # Проверяем, является ли промпт пустышкой DummyPrompt
    #             is_dummy = (
    #                 hasattr(prompt, "__class__") and prompt.__class__.__name__ == "DummyPrompt"
    #             )
    #             prompt_status = "⚠️ Dummy (Файл потерян в prompts)" if is_dummy else f"✅ {prompt}"

    #             print(
    #                 f"      [Сцена {idx + 1}] order: {order} | Аудио: {track} | Картинка: {prompt_status}"
    #             )
    #     else:
    #         print("   👉 В шаблон уходит пустой список таймлайна.")

    #     print("=" * 60 + "\n")

    # except Exception as e:
    #     print(f"❌ Ошибка при выполнении диагностики конфигурации: {str(e)}")
