from django.conf import settings
from ai_inspector.models import AIProvider

# Импорты клиентов
try:
    from tavily import TavilyClient

    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

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


class ResearchValidationError(ValueError):
    """Исключение для ошибок валидации исследовательских данных."""

    pass


def generate_text(provider_name, prompt, max_tokens=2500, temperature=0.7, **kwargs):
    """
    Универсальная функция генерации текста.
    Автоматически выбирает клиент (OpenAI, HuggingFace, etc.) на основе названия провайдера.
    """
    print(f"🤖 [SERVICES] Запрос к провайдеру: {provider_name}")

    # 1. Получаем конфигурацию из БД
    try:
        provider_obj = AIProvider.objects.get(name=provider_name, is_active=True)
    except AIProvider.DoesNotExist:
        raise ValueError(f"Provider '{provider_name}' not found or inactive in DB.")

    config = provider_obj.config or {}
    api_key = provider_obj.get_api_key()  # Твой метод получения ключа

    if not api_key and provider_name != "huggingface":  # HF может работать без ключа лимитировано
        raise ValueError(f"API Key missing for provider '{provider_name}'.")

    # 2. ЛОГИКА ВЫБОРА КЛИЕНТА

    # --- ВАРИАНТ A: OPENAI (и совместимые API через base_url) ---
    if provider_name.lower() == "openai" or config.get("api_type") == "openai":
        if not OPENAI_AVAILABLE:
            raise ImportError("Package 'openai' is not installed. Run: pip install openai")

        model_id = kwargs.pop("model", config.get("model_id") or config.get("model"))
        # model_id = config.get("model_id") or config.get("model")
        if not model_id:
            raise ValueError(f"No model specified for OpenAI provider. Config: {config}")

        base_url = config.get("base_url") or "https://api.openai.com/v1"

        print(f"   -> Используем OpenAI клиент. Модель: {model_id}, URL: {base_url}")

        client = OpenAI(api_key=api_key, base_url=base_url)
        model_id = kwargs.pop("model", None) or config.get("model_id") or config.get("model")
        # Новые модели (gpt-4o, gpt-5, o1, o3) требуют max_completion_tokens
        # Старые модели (gpt-3.5, gpt-4) используют max_tokens
        model_lower = model_id.lower()
        is_new_model = any(x in model_lower for x in ["gpt-4o", "gpt-5", "o1", "o3", "o4"])

        # Формируем параметры запроса
        create_params = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        # Добавляем правильный параметр лимита токенов
        if is_new_model:
            create_params["max_completion_tokens"] = max_tokens
        else:
            create_params["max_tokens"] = max_tokens

        # Опционально: response_format, если передан через kwargs
        response_format = kwargs.pop("response_format", None)
        if response_format:
            create_params["response_format"] = response_format

        try:
            response = client.chat.completions.create(**create_params)
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenAI Error: {e}")
            raise e

    # --- ВАРИАНТ B: HUGGINGFACE (Default) ---
    elif provider_name.lower() == "huggingface":
        if not HF_AVAILABLE:
            raise ImportError("Package 'huggingface_hub' is not installed.")

        model_id = config.get("model_id") or config.get("text_model")
        # Для HF модель обязательна, если не используем роутинг (но лучше указывать)
        if not model_id:
            # Попытка взять из дефолтных настроек Django если есть
            model_id = getattr(settings, "HF_DEFAULT_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
            print(f"   -> Модель не указана в конфиге, используем дефолт: {model_id}")

        # Если нужен кастомный эндпоинт (например, локальный TGI)
        base_url = config.get("base_url")

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
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ HuggingFace Error: {e}")
            raise e

    # --- ВАРИАНТ C: GOOGLE GEMINI (Заготовка) ---
    elif provider_name.lower() == "google" or provider_name.lower() == "gemini":
        # Здесь можно добавить логику для google-generativeai
        raise NotImplementedError(
            "Google Gemini support not implemented yet in this service function."
        )
    # --- ВАРИАНТ D: TAVILY (Search) ---
    elif provider_name.lower() == "tavily_search":
        if not TAVILY_AVAILABLE:
            raise ImportError("Package 'tavily' is not installed. Run: pip install tavily")

        client = TavilyClient(api_key=api_key)
        try:
            print(f"   🔍 Tavily: поиск по запросу '{prompt[:80]}...'")

            # Количество результатов
            max_result = kwargs.pop("max_results", None)
            include_domains = kwargs.pop("include_domains", None)
            exclude_domains = kwargs.pop("exclude_domains", None)

            if max_result is None:
                max_result = 20
            # Формируем параметры поиска
            search_params = {
                "query": prompt,
                "max_results": max_result,
                "include_raw_content": False,
                "include_answer": True,
                "include_images": True,
            }
            # Добавляем домены, если переданы
            if include_domains:
                search_params["include_domains"] = include_domains
                print(f"   🎯 Поиск ТОЛЬКО на: {', '.join(include_domains)}")

            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
                print(
                    f"   🚫 Исключаем: {', '.join(exclude_domains[:5])}{'...' if len(exclude_domains) > 5 else ''}"
                )

            response = client.search(**search_params)
            return response
        except Exception as e:
            error_msg = f"Критическая ошибка поиска Tavily: {e}"
            print(f"❌ [RESEARCH] {error_msg}")
            # ✅ ОСТАНОВКА ПРОЦЕССА: выбрасываем ошибку, не продолжаем без веб-данных
            raise ResearchValidationError(error_msg)
    else:
        raise ValueError(
            f"Unknown or unsupported provider type: {provider_name}. Use 'openai' or 'huggingface'."
        )


def search_with_tavily(
    query: str,
    provider_name: str = "tavily_search",
    max_results: int = 7,
    **kwargs,
) -> dict:
    """
    Удобная обёртка для поиска через Tavily.
    Возвращает словарь с ключами: answer, results (список), sources.
    """
    include_domains = kwargs.pop("include_domains", None)
    exclude_domains = kwargs.pop("exclude_domains", None)

    raw_response = generate_text(
        provider_name=provider_name,
        prompt=query,
        max_tokens=max_results,  # тут это число результатов, не токенов
        include_domains=include_domains,  # 🔥 Передаём дальше
        exclude_domains=exclude_domains,  # 🔥 Передаём дальше
        include_images=True,  # Передаем параметр для сбора картинок
    )
    # Нормализуем ответ Tavily в удобный формат
    answer = raw_response.get("answer", "") if isinstance(raw_response, dict) else ""
    results = raw_response.get("results", []) if isinstance(raw_response, dict) else []
    images = raw_response.get("images", []) if isinstance(raw_response, dict) else []

    # Извлекаем только нужные поля из каждого результата (экономим память)
    clean_results = []
    for r in results:
        clean_results.append(
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),  # это snippet, не весь HTML
                "score": r.get("score", 0),
            }
        )

    return {
        "answer": answer,
        "results": clean_results,
        "sources_count": len(clean_results),
        "images": images,  # 🔥 Возвращаем изображения
    }
