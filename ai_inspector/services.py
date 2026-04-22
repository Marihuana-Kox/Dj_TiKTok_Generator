from .models import AIProvider
from .utils import decrypt_key
from .backends.base import BACKEND_REGISTRY

# Импорт бэкендов для регистрации (дублируем для надежности, если apps.py не сработает)
try:
    from .backends import huggingface, openai
except ImportError:
    pass


def get_available_providers():
    """Возвращает список имен активных провайдеров (Пересечение: Код + БД)."""
    registered_names = set(BACKEND_REGISTRY.keys())
    active_db_names = set(
        AIProvider.objects.filter(
            is_active=True).values_list('name', flat=True)
    )
    return list(registered_names.intersection(active_db_names))


def get_backend(provider_name: str):
    """Создает экземпляр бэкенда."""
    # 1. Есть ли код?
    backend_class = BACKEND_REGISTRY.get(provider_name)
    if not backend_class:
        raise NotImplementedError(f"Бэкенд '{provider_name}' не реализован.")

    # 2. Есть ли в БД и активен?
    try:
        provider = AIProvider.objects.get(name=provider_name)
    except AIProvider.DoesNotExist:
        raise ValueError(f"Провайдер '{provider_name}' не найден в БД.")

    if not provider.is_active:
        raise PermissionError(f"Провайдер '{provider_name}' отключен.")

    # 3. Расшифровка и запуск
    api_key = decrypt_key(provider.api_key)
    # Передаем весь объект provider, как в твоем коде HF
    return backend_class(api_key=api_key, config=provider.config)


def generate_text(provider_name: str, prompt: str, **kwargs) -> str:
    backend = get_backend(provider_name)
    return backend.generate_text(prompt, **kwargs)


def generate_image(provider_name: str, prompt: str, **kwargs) -> bytes:
    backend = get_backend(provider_name)
    return backend.generate_image(prompt, **kwargs)
