from django.db import models
from django.core.exceptions import ValidationError
from .utils import encrypt_key, decrypt_key


class AIProvider(models.Model):
    PROVIDER_TYPES = [
        ('llm', 'Текст / LLM'),
        ('image', 'Изображения'),
        ('audio', 'Аудио / Голос'),
        ('video', 'Видео'),
    ]

    name = models.CharField("Кодовое имя", max_length=50, unique=True,
                            help_text="Например: openai, gemini, hf")
    display_name = models.CharField("Отображаемое имя", max_length=100)
    provider_type = models.CharField(
        "Тип", max_length=20, choices=PROVIDER_TYPES)

    api_key = models.TextField(
        "API Key (Зашифрован)", blank=True, editable=False)
    base_url = models.URLField("Base URL", blank=True, null=True)
    config = models.JSONField("Конфигурация", default=dict, blank=True)

    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Провайдер"
        verbose_name_plural = "AI Провайдеры"
        ordering = ['provider_type', 'name']

    def __str__(self):
        return f"{self.display_name} ({self.provider_type})"

    def set_api_key(self, raw_key: str):
        self.api_key = encrypt_key(raw_key)

    def get_api_key(self) -> str:
        return decrypt_key(self.api_key)

    def clean(self):
        if not self.name.islower() or ' ' in self.name:
            raise ValidationError(
                "Кодовое имя должно быть в lowercase без пробелов.")
