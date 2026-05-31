import os
import json
import django
from pathlib import Path
import mutagen

# Инициализируем настройки Django, чтобы скрипт имел доступ к базе данных
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "tiktok_web.settings"
)  # Проверь имя своего таргет-модуля настроек
django.setup()

from django.apps import apps

AudioTrack = apps.get_model(
    "audio", "AudioTrack"
)  # Замени 'генератор' на имя твоего Django-приложения (app_name)

# Настройки путей конкретного проекта
PROJECT_DIR = Path("media/projects/opasnye_eksperimenty_v_sukhume")
OLD_VOICES_DIR = PROJECT_DIR / "voices_ru"
NEW_VOICE_DIR = PROJECT_DIR / "voice_ru"
NEW_JSON_PATH = NEW_VOICE_DIR / "voices_meta_ru.json"


def migrate_project_to_fixed_ordnung():
    print("=== ЗАПУСК ПОЛНОЙ МИГРАЦИИ И ИСПРАВЛЕНИЯ ПУТЕЙ ===")

    # 1. Создаем правильную целевую папку voice_ru, если её нет
    NEW_VOICE_DIR.mkdir(parents=True, exist_ok=True)

    # Скелет для нового voices_meta_ru.json
    meta_data = {"paragraphs": {}}

    # Вытаскиваем из базы все треки, принадлежащие статье/проекту (Сухум имеет article_id=118 или проект id=38)
    # Для точности выберем треки, у которых относительный путь содержит старую папку 'voices_ru'
    tracks = AudioTrack.objects.filter(audio_file__contains="opasnye_eksperimenty_v_sukhume")

    if not tracks.exists():
        print("❌ Треки для данного проекта не найдены в БД.")
        return

    for track in tracks:
        # Определяем орднунг и имя спикера
        track_order = track.order
        voice_id = getattr(track, "speaker_name", None)
        if not voice_id or voice_id in ["Manual", "success", ""]:
            voice_id = "noname"  # Твоё имя по умолчанию

        language = "ru"  # В данном случае жестко ru

        # Вычисляем оригинальное расширение файла на диске
        # Смотрим, что сейчас лежит в старой или новой папке
        old_file_wav = OLD_VOICES_DIR / f"voice_{track.id}.wav"

        # Выясняем, какое расширение у нас фактически (проверяем по сигнатуре файла, если он существует)
        ext = ".wav"
        source_file_path = None

        if old_file_wav.exists():
            source_file_path = old_file_wav
            with open(old_file_wav, "rb") as f_check:
                if f_check.read(4)[:4] != b"RIFF":
                    ext = ".mp3"
        elif (OLD_VOICES_DIR / f"voice_{track.id}.mp3").exists():
            source_file_path = OLD_VOICES_DIR / f"voice_{track.id}.mp3"
            ext = ".mp3"
        elif (NEW_VOICE_DIR / f"voice_{track.id}.wav").exists():
            source_file_path = NEW_VOICE_DIR / f"voice_{track.id}.wav"
            # Проверим и тут
            with open(source_file_path, "rb") as f_check:
                if f_check.read(4)[:4] != b"RIFF":
                    ext = ".mp3"
        elif (NEW_VOICE_DIR / f"voice_{track.id}.mp3").exists():
            source_file_path = NEW_VOICE_DIR / f"voice_{track.id}.mp3"
            ext = ".mp3"

        # Новое каноничное имя файла по орднунгу
        new_filename = f"{voice_id}_{track_order}_{language}{ext}"
        destination_file_path = NEW_VOICE_DIR / new_filename

        # Переносим и переименовываем файл физически
        if source_file_path and source_file_path.exists():
            if source_file_path != destination_file_path:
                os.rename(source_file_path, destination_file_path)
                print(f"Файл {source_file_path.name} -> успешно перенесен как {new_filename}")
        else:
            print(
                f"⚠️ Физический файл для трека {track.id} не найден на диске, генерируем метаданные по остаточным данным."
            )

        # Считаем длительность клипа для таймлайна через mutagen
        duration = 0.0
        if destination_file_path.exists():
            try:
                audio_info = mutagen.File(destination_file_path)
                if audio_info is not None and audio_info.info is not None:
                    duration = round(audio_info.info.length, 2)
            except Exception as e:
                print(f"Не удалось посчитать длительность для {new_filename}: {e}")

        # Обновляем пути в Базе Данных Django (меняем voices_ru на voice_ru и ставим новое имя файла)
        new_audio_url = f"/media/projects/opasnye_eksperimenty_v_sukhume/voice_ru/{new_filename}"
        track.audio_file = new_audio_url
        if hasattr(track, "duration"):
            track.duration = duration
        track.save()

        # Формируем структуру параграфа в JSON точь-в-точь как в генераторе
        meta_data["paragraphs"][str(track_order)] = {
            "article_title": track.project.title,
            "article_id": track.project.article.id if track.project.article else 0,
            "track_order": track_order,
            "speaker": voice_id,
            "language": language,
            "model": "manual",
            "speed": 1.0,
            "full_text": track.text,
            "duration": duration,  # Длина теперь железно внутри JSON клипа
        }

    # Записываем новый файл метаданных voices_meta_ru.json
    with open(NEW_JSON_PATH, "w", encoding="utf-8") as jf:
        json.dump(meta_data, jf, ensure_ascii=False, indent=4, sort_keys=True)

    print(f"✅ Новый файл метаданных успешно создан: {NEW_JSON_PATH}")

    # Удаляем старую пустую папку voices_ru и старый некорректный json за ненадобностью
    try:
        old_json = PROJECT_DIR / "metadata_ru.json"
        if old_json.exists():
            os.remove(old_json)
        if OLD_VOICES_DIR.exists() and not os.listdir(OLD_VOICES_DIR):
            os.rmdir(OLD_VOICES_DIR)
            print("🗑 Старая пустая папка voices_ru удалена.")
    except Exception as e:
        print(f"⚠️ Не удалось удалить старые директории/файлы: {e}")

    print(
        "\n🚀 МИГРАЦИЯ ЗАВЕРШЕНА! База данных обновлена, файлы перенесены. Обнови страницу редактора."
    )


if __name__ == "__main__":
    migrate_project_to_fixed_ordnung()
