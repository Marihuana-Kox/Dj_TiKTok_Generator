from django.apps import AppConfig


class AiInspectorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_inspector'

    def ready(self):
        # Импортируем бэкенды ТОЛЬКО для регистрации классов.
        # Это заполнит BACKEND_REGISTRY перед первым запросом.
        try:
            from .backends import huggingface, openai
            # Когда добавишь другие, просто раскомментируй:
            # from .backends import gemini, qwen
            print("✅ AI Backends registered successfully.")
        except ImportError as e:
            print(f"⚠️ Warning: Could not load some backends: {e}")
