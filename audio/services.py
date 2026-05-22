import re
import json
import logging
import os
from pathlib import Path

import requests
from ai_inspector.models import AIProvider
from elevenlabs import ElevenLabs, Voice, VoiceSettings
from elevenlabs.core import ApiError
from django.core.cache import cache
from django.conf import settings
from asgiref.sync import async_to_sync
from inworld_tts import InworldTTS

from image.services import get_or_create_project_dir

logger = logging.getLogger(__name__)


def split_text_by_words_and_dots(text: str, target_word_count: int = 50) -> list:
    """
    Разбивает текст на сюжеты примерно по target_word_count слов,
    но делает срез строго на окончаниях предложений (. ! ?).
    """
    # Регулярка делит текст на предложения, сохраняя знаки препинания
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence_words = sentence.split()
        if not sentence_words:
            continue

        current_chunk.append(sentence)
        current_word_count += len(sentence_words)

        # Если набрали нужный лимит слов — закрываем сюжет
        if current_word_count >= target_word_count:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_word_count = 0

    # Дописываем остаток, если он есть
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def generate_voiceover_inworld(
    text: str,
    provider_instance,
    voice_id: str,  # Имя спикера, например 'Nikolay'
    language: str,  # Локаль, например 'ru'
    project_title: str,  # Название статьи
    article_id: int,  # ID проекта/статьи для get_or_create_project_dir
    track_order: int = 1,  # 🔥 НАШ ОРДНУНГ: Порядковый номер фрагмента текста!
    speaking_rate: float = 1.0,
    task_id: str = None,
) -> str:
    cache_key = f"progress_{task_id}" if task_id else None

    def log_to_modal(message: str, percent: int = None):
        if cache_key:
            current_data = cache.get(cache_key, {})
            if "logs" not in current_data:
                current_data["logs"] = []
            current_data["logs"].append(message)
            if percent:
                current_data["percent"] = percent
            cache.set(cache_key, current_data, 3600)

    try:
        if not text or not text.strip():
            raise ValueError("Текст пуст")

        log_to_modal("🛠 Сбор конфигурации провайдера из БД...", percent=25)

        api_key = provider_instance.api_key
        config = getattr(provider_instance, "config", {}) or {}
        if not api_key:
            raise ValueError("Ключ API в базе не найден")
        clean_key = api_key.strip()

        model_id = config.get("model_id", "inworld-tts-2")

        # === ОГРАНИЧЕНИЕ НА 10 СЛОВ ДЛЯ ТЕСТИРОВАНИЯ ===
        short_text = " ".join(text.split())
        print(f"📤 Payload для теста (10 слов): {short_text}")
        # ===============================================

        async def _async_stream_generate():
            log_to_modal(
                f"📡 Инициализация Inworld SDK ({model_id}). Подключение к стриму...",
                percent=57,
            )
            tts = InworldTTS(api_key=clean_key)
            chunks = []

            async for chunk in tts.stream(
                text=short_text,
                voice=voice_id,
                encoding="WAV",
                sample_rate=48000,
            ):
                chunks.append(chunk)
                log_to_modal(f"📥 Получен аудио-пакет: {len(chunk)} байт")

            if not chunks:
                raise ValueError("Сервер Inworld вернул пустой аудио-поток.")

            return b"".join(chunks)

        print("🔥 [INWORLD SDK] Запуск асинхронного генератора", flush=True)
        audio_content = async_to_sync(_async_stream_generate)()

        log_to_modal("💾 Сохранение файлов в структуру проекта...", percent=69)

        # 1. Находим/создаем главную папку проекта по РУССКОМУ названию статьи
        project_dir, folder_name = get_or_create_project_dir(project_title, article_id)

        # 2. Динамически формируем имя подпапки: voice_ru, voice_en
        voice_folder_name = f"voice_{language}" if language else "voice"
        voice_dir = Path(project_dir) / voice_folder_name
        voice_dir.mkdir(parents=True, exist_ok=True)

        # 3. 🔥 ИСПРАВЛЕНО: Сразу формируем имя файла с порядковым номером (Орднунгом)
        # Получится: Nikolay_1_ru
        file_base_name = f"{voice_id}_{track_order}_{language}"
        filename = f"{file_base_name}.wav"
        json_filename = f"voices_meta_{language}.json"

        file_path = voice_dir / filename
        json_path = voice_dir / json_filename

        # Записываем аудиофайл
        with open(file_path, "wb") as f:
            f.write(audio_content)

        # Читаем существующий файл или создаем новый скелет
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    meta_data = json.load(jf)
            except Exception:
                meta_data = {"paragraphs": {}}
        else:
            meta_data = {"paragraphs": {}}

        if "paragraphs" not in meta_data:
            meta_data["paragraphs"] = {}
        # 4. Создаем конфигурационный .json для субтитров текущего фрагмента
        meta_data["paragraphs"][str(track_order)] = {
            "article_title": project_title,
            "article_id": article_id,
            "track_order": track_order,
            "speaker": voice_id,
            "language": language,
            "model": model_id,
            "speed": speaking_rate,
            "full_text": text,
        }

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(meta_data, jf, ensure_ascii=False, indent=4, sort_keys=True)

        logger.info(f"✅ Аудио и конфиг успешно сохранены в: {voice_dir}", percent=89)

        log_to_modal(f"🎉 Озвучка сохранена в проект: {voice_folder_name}/{filename}", percent=95)

        return f"projects/{folder_name}/{voice_folder_name}/{filename}"

    except Exception as e:
        logger.error(f"❌ Ошибка генерации озвучки: {e}")
        raise RuntimeError(f"Ошибка генерации озвучки: {e}")


def generate_voiceover_elevenlabs(
    text: str, project_id: str = None, provider_name: str = "elevenlabs"
) -> str:
    if not text or not text.strip():
        raise ValueError("Текст для озвучки пуст")

    # 1. Читаем конфиг провайдера из БД
    provider = AIProvider.objects.filter(name=provider_name, is_active=True).first()
    if not provider:
        raise ValueError(f"Провайдер '{provider_name}' не найден или отключён в БД")

    api_key = provider.api_key
    model_id = provider.model_id or "eleven_multilingual_v2"

    config = getattr(provider, "config", {}) or {}
    voice_id = config.get("default_voice", "21m00Tcm4TlvDq8ikWAM")  # ← Из БД!
    stability = float(config.get("stability", 0.5))
    similarity_boost = float(config.get("similarity_boost", 0.75))

    client = ElevenLabs(api_key=api_key)
    voice_settings = VoiceSettings(stability=stability, similarity_boost=similarity_boost)

    try:
        audio_stream = client.generate(
            text=text.strip(),
            voice=Voice(voice_id=voice_id, settings=voice_settings),
            model=model_id,
        )

        project_id = project_id or "default"
        save_dir = Path(settings.MEDIA_ROOT) / "audio_projects" / str(project_id)
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = f"voiceover_{project_id}_{os.urandom(4).hex()}.mp3"
        file_path = save_dir / filename

        with open(file_path, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)

        logger.info(f"✅ ElevenLabs аудио сохранено: {file_path}")
        return f"audio_projects/{project_id}/{filename}"

    except ApiError as e:
        err_str = str(e).lower()
        if "quota" in err_str or "character limit" in err_str:
            raise ValueError("⛔ Лимит символов ElevenLabs исчерпан. Пополните баланс.")
        logger.error(f"❌ ElevenLabs API ошибка: {e}")
        raise RuntimeError(f"Ошибка генерации озвучки: {e}")
