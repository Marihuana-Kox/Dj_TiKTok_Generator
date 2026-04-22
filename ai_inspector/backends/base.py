from abc import ABC, abstractmethod

# Глобальный реестр доступных классов бэкендов
# Ключ: имя провайдера (строка), Значение: Класс
BACKEND_REGISTRY = {}


def register_backend(name: str):
    """Декоратор для регистрации бэкенда."""
    def decorator(cls):
        BACKEND_REGISTRY[name] = cls
        return cls
    return decorator


class BaseAIBackend(ABC):
    # Имя провайдера должно быть указано в наследнике
    provider_name = None

    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.config = config

    @abstractmethod
    def generate_text(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    def generate_image(self, prompt: str, **kwargs) -> bytes:
        pass

    def validate_connection(self) -> bool:
        try:
            self.generate_text("Test", max_tokens=5)
            return True
        except:
            return False
