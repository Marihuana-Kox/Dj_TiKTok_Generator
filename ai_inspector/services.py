import json
from django.conf import settings
from ai_inspector.models import AIProvider

# Импорты клиентов
try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Можно добавить Google Gemini, Anthropic и т.д. по аналогии


def generate_text(provider_name, prompt, max_tokens=2500, temperature=0.7):
    """
    Универсальная функция генерации текста.
    Автоматически выбирает клиент (OpenAI, HuggingFace, etc.) на основе названия провайдера.
    """
    print(f"🤖 [SERVICES] Запрос к провайдеру: {provider_name}")

    # 1. Получаем конфигурацию из БД
    try:
        provider_obj = AIProvider.objects.get(
            name=provider_name, is_active=True)
    except AIProvider.DoesNotExist:
        raise ValueError(
            f"Provider '{provider_name}' not found or inactive in DB.")

    config = provider_obj.config or {}
    api_key = provider_obj.get_api_key()  # Твой метод получения ключа

    if not api_key and provider_name != 'huggingface':  # HF может работать без ключа лимитировано
        raise ValueError(f"API Key missing for provider '{provider_name}'.")

    # 2. ЛОГИКА ВЫБОРА КЛИЕНТА

    # --- ВАРИАНТ A: OPENAI (и совместимые API через base_url) ---
    if provider_name.lower() == 'openai' or config.get('api_type') == 'openai':
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "Package 'openai' is not installed. Run: pip install openai")

        model_id = config.get('model_id') or config.get('model')
        if not model_id:
            raise ValueError(
                f"No model specified for OpenAI provider. Config: {config}")

        base_url = config.get('base_url') or "https://api.openai.com/v1"

        print(
            f"   -> Используем OpenAI клиент. Модель: {model_id}, URL: {base_url}")

        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenAI Error: {e}")
            raise e

    # --- ВАРИАНТ B: HUGGINGFACE (Default) ---
    elif provider_name.lower() == 'huggingface':
        if not HF_AVAILABLE:
            raise ImportError("Package 'huggingface_hub' is not installed.")

        model_id = config.get('model_id') or config.get('text_model')
        # Для HF модель обязательна, если не используем роутинг (но лучше указывать)
        if not model_id:
            # Попытка взять из дефолтных настроек Django если есть
            model_id = getattr(settings, 'HF_DEFAULT_MODEL',
                               'meta-llama/Llama-3.1-8B-Instruct')
            print(
                f"   -> Модель не указана в конфиге, используем дефолт: {model_id}")

        # Если нужен кастомный эндпоинт (например, локальный TGI)
        base_url = config.get('base_url')

        print(f"   -> Используем HuggingFace клиент. Модель: {model_id}")

        # Инициализация клиента HF
        if base_url:
            # Если указан свой URL (например, локальный сервер), используем его
            client = InferenceClient(base_url=base_url, token=api_key)
        else:
            # Стандартный облачный HF
            client = InferenceClient(token=api_key)

        try:
            response = client.chat_completion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ HuggingFace Error: {e}")
            raise e

    # --- ВАРИАНТ C: GOOGLE GEMINI (Заготовка) ---
    elif provider_name.lower() == 'google' or provider_name.lower() == 'gemini':
        # Здесь можно добавить логику для google-generativeai
        raise NotImplementedError(
            "Google Gemini support not implemented yet in this service function.")

    else:
        raise ValueError(
            f"Unknown or unsupported provider type: {provider_name}. Use 'openai' or 'huggingface'.")
