import base64
import logging
import os
from pathlib import Path

import requests
from ai_inspector.models import AIProvider
from elevenlabs import ElevenLabs, Voice, VoiceSettings
from elevenlabs.core import ApiError
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_voiceover_inworld(
    text: str,
    provider_instance,
    voice_id: str,
    language: str,
    speaking_rate: float = 1.0,
    folder_name: str = "default",
) -> str:
    print("🔥 [SERVICE START] Функция вызвана!", flush=True)

    try:
        print(f"🔍 Проверка провайдера: '{provider_instance.name}...'")
        print(f"🔍 Проверка провайдера: '{provider_instance.display_name}...'")

        # Логируем начало текста
        if not text or not text.strip():
            raise ValueError("Текст пуст")

        # URL и API ключ берем из основных полей модели
        url = provider_instance.base_url or "https://api.inworld.ai/tts/v1/voice333"
        api_key = provider_instance.api_key
        print(f"🔑  Это наш: {url}")
        # Достаем твой JSON-конфиг
        config = getattr(provider_instance, "config", {}) or {}

        # БЕРЕМ ДАННЫЕ ИЗ ТВОЕГО КОНФИГА (с защитой от отсутствия ключей)
        model_id = config.get("model_id", "inworld-tts-2")
        delivery_mode = config.get("delivery_mode", "BALANCED")
        timestamp_type = config.get("timestamp_type", "WORD")

        headers = {
            "Authorization": f"Basic {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "text": " ".join(text.split()[:10]),
            "voiceId": voice_id,
            "modelId": model_id,
            "timestampType": timestamp_type,
            "audioConfig": {"speakingRate": speaking_rate},
            "deliveryMode": delivery_mode,
            "language": language,
        }
        print("📤 Payload для:", payload["text"])
        # Для отладки в терминале VS Code при запросе к "пустому" серверу
        print(f"📡 Отправка запроса на: {url}")

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        # ... (дальше логика сохранения файла)
        result = response.json()

        if "audioContent" not in result:
            raise ValueError("Ответ API не содержит audioContent")

        # Декодируем аудио
        audio_content = base64.b64decode(result["audioContent"])

        # --- ЛОГИКА ПАПОК ---
        # media/voice/название_статьи/
        save_dir = Path(settings.MEDIA_ROOT) / "voice" / folder_name
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{voice_id}_{language}_{os.urandom(2).hex()}.mp3"
        file_path = save_dir / filename

        with open(file_path, "wb") as f:
            f.write(audio_content)

        logger.info(f"✅ Аудио сохранено: {file_path}")

        # Возвращаем относительный путь для сохранения в БД/вывода в шаблон
        return f"voice/{folder_name}/{filename}"
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка запроса к Inworld: {e}")
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
    voice_settings = VoiceSettings(
        stability=stability, similarity_boost=similarity_boost
    )

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
