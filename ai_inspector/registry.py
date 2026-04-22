from .backends.openai import OpenAIBackend
from .backends.gemini import GeminiBackend
from .backends.huggingface import HuggingFaceBackend

BACKEND_REGISTRY = {
    'openai': OpenAIBackend,
    'gemini': GeminiBackend,
    'huggingface': HuggingFaceBackend,
}


def get_backend_class(provider_name: str):
    if provider_name not in BACKEND_REGISTRY:
        raise ValueError(f"Unknown backend: {provider_name}")
    return BACKEND_REGISTRY[provider_name]
