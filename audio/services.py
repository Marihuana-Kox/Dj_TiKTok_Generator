import base64
import re
import json
import logging
import os
from pathlib import Path

import mutagen
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


def clean_voice_name(voice_id: str) -> str:
    """
    Извлекает чистое имя голоса из полного ID.

    Примеры:
    - 'default-jkassdf23jk__marfa_new' → 'Marfa'
    - 'Nikolai' → 'Nikolai'
    - 'elevenlabs__abc123__elena' → 'Elena'
    """
    if not voice_id:
        return "Unknown"

    # Берём часть после последнего '__' (если есть)
    clean_name = voice_id.split("__")[-1]

    # Берём только первое слово (до первого '_')
    clean_name = clean_name.split("_")[0]

    # Делаем первую букву заглавной
    return clean_name.title() if clean_name else "Unknown"


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
    voice_id: str,
    language: str,
    project_title: str,
    article_id: int,
    track_order: int = 1,
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

        log_to_modal(" Сбор конфигурации провайдера из БД...", percent=25)

        api_key = provider_instance.api_key
        config = getattr(provider_instance, "config", {}) or {}

        if not api_key:
            raise ValueError("Ключ API в базе не найден")

        # 🔥 1. ПОЛУЧАЕМ URL ИЗ МОДЕЛИ AIProvider
        # Если поле base_url пусто, используем стандартный эндпоинт Inworld
        api_url = provider_instance.base_url or "https://api.inworld.ai/tts/v1/voice"

        # 🔥 2. ГИБКОЕ ЧТЕНИЕ ПАРАМЕТРОВ ИЗ JSON CONFIG (поддержка camelCase и snake_case)
        model_id = config.get("modelId") or config.get("model_id", "inworld-tts-2")
        delivery_mode = config.get("deliveryMode") or config.get("delivery_mode", "BALANCED")
        timestamp_type = config.get("timestampType") or config.get("timestamp_type", "WORD")

        audio_config = config.get("audioConfig", {}) or {}
        rate_local = float(
            audio_config.get("speakingRate")
            or audio_config.get("speaking_rate")
            or config.get("speakingRate")
            or config.get("speaking_rate")
            or speaking_rate
        )
        encoding = audio_config.get("audioEncoding") or audio_config.get("audio_encoding", "WAV")

        # Формируем локаль ru-RU если пришел просто 'ru'
        lang_code = language.upper() if len(language) == 2 else language
        locale = f"{language}-{lang_code}" if "-" not in language else language

        # 🔥 ОТЛАДОЧНЫЙ ВЫВОД РЕАЛЬНЫХ ПАРАМЕТРОВ В КОНСОЛЬ
        print("\n" + "=" * 80)
        print(f"🔍 [INWORLD DEBUG] Параметры для REST API:")
        print(f"    URL      : {api_url}")
        print(f"   🤖 Model ID : {model_id}")
        print(f"   🎙️ Voice ID : {voice_id}")
        print(f"   🎛️ Delivery : {delivery_mode}")
        print(f"   ⚡ Rate     : {rate_local}")
        print(f"   💾 Encoding : {encoding}")
        print(f"   📝 Text len : {len(text)} символов")
        print("=" * 80 + "\n")

        log_to_modal(f"📡 Отправка запроса в Inworld REST API ({model_id})...", percent=57)

        # 🔥 3. ФОРМИРУЕМ PAYLOAD В ФОРМАТЕ REST API (camelCase)
        # Важно: text.strip() сохраняет пунктуацию, что критично для интонаций
        payload = {
            "text": text.strip(),
            "voiceId": voice_id,
            "modelId": model_id,
            "language": locale,
            "deliveryMode": delivery_mode,
            "timestampType": timestamp_type,
            "audioConfig": {"speakingRate": rate_local, "audioEncoding": encoding},
        }

        # 🔥 4. ОБРАБОТКА АВТОРИЗАЦИИ
        # Проверяем формат ключа. Если это client:secret, кодируем в Base64.
        # Если уже Base64 или начинается с Basic, используем как есть.
        auth_header = api_key.strip()
        if ":" in auth_header and not auth_header.startswith("Basic "):
            encoded = base64.b64encode(auth_header.encode()).decode()
            auth_header = f"Basic {encoded}"
        elif not auth_header.startswith("Basic "):
            # Предполагаем, что это уже готовый токен или ключ, который нужно обернуть
            # Для Inworld обычно требуется Basic Auth из ClientID:ClientSecret
            auth_header = f"Basic {auth_header}"

        response = requests.post(
            api_url,  # 🔥 ИСПОЛЬЗУЕМ URL ИЗ БД
            json=payload,
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        if "audioContent" not in result:
            raise ValueError("API вернул ответ без аудио-контента")

        audio_content = base64.b64decode(result["audioContent"])
        ext = ".mp3" if encoding == "MP3" else ".wav"

        log_to_modal("💾 Сохранение файлов в структуру проекта...", percent=69)

        # 5. СОХРАНЕНИЕ ФАЙЛОВ И МЕТАДАННЫХ
        project_dir, folder_name = get_or_create_project_dir(project_title, article_id)

        voice_folder_name = f"voice_{language}" if language else "voice"
        voice_dir = Path(project_dir) / voice_folder_name
        voice_dir.mkdir(parents=True, exist_ok=True)

        clean_voice = clean_voice_name(voice_id)
        file_base_name = f"{clean_voice}_{track_order}_{language}"
        filename = f"{file_base_name}{ext}"
        json_filename = f"voices_meta_{language}.json"

        file_path = voice_dir / filename
        json_path = voice_dir / json_filename

        with open(file_path, "wb") as f:
            f.write(audio_content)

        # Вычисляем длительность
        duration = 0.0
        try:
            audio_info = mutagen.File(file_path)
            if audio_info is not None and audio_info.info is not None:
                duration = round(audio_info.info.length, 2)
        except Exception as audio_err:
            logger.warning(f"⚠️ Ошибка подсчета длины при генерации: {audio_err}")

        # Работа с JSON метаданными
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

        meta_data["paragraphs"][str(track_order)] = {
            "article_title": project_title,
            "article_id": article_id,
            "track_order": track_order,
            "speaker": voice_id,
            "speaker_clean": clean_voice,
            "language": language,
            "model": model_id,
            "speed": rate_local,
            "full_text": text,
            "duration": duration,
        }

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(meta_data, jf, ensure_ascii=False, indent=4, sort_keys=True)

        logger.info(f"✅ Аудио успешно сохранено в: {voice_dir}")
        log_to_modal(f"🎉 Озвучка сохранена: {voice_folder_name}/{filename}", percent=95)

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
