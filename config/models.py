from django.db import models


class SystemConfig(models.Model):
    """
    Глобальные настройки системы.
    В базе данных должна быть всего ОДНА запись этого типа.
    """

    # --- Режим работы ---
    MODE_CHOICES = [
        ('manual', '🛠 Ручной (Пошаговый контроль)'),
        ('auto', '🤖 Полный Автопилот (One-Click)'),
    ]
    operation_mode = models.CharField(
        "Режим работы", max_length=10, choices=MODE_CHOICES, default='manual')

    # --- API Ключи (храним как текст) ---
    openai_key = models.CharField(
        "OpenAI API Key", max_length=255, blank=True, help_text="sk-...")
    gemini_key = models.CharField(
        "Google Gemini API Key", max_length=255, blank=True)
    hf_key = models.CharField("HuggingFace API Key",
                              max_length=255, blank=True, help_text="hf_...")
    elevenlabs_key = models.CharField(
        "ElevenLabs API Key (Voice)", max_length=255, blank=True)

    # --- Настройки Моделей ---
    ARTICLE_MODEL_CHOICES = [
        ('gpt-4o', 'GPT-4o (Best Quality)'),
        ('gpt-4o-mini', 'GPT-4o Mini (Fast/Cheap)'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash (Fast)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro (Smart)'),
    ]
    default_article_model = models.CharField(
        "Модель для статей", max_length=50, choices=ARTICLE_MODEL_CHOICES, default='gpt-4o')

    IMAGE_MODEL_CHOICES = [
        ('flux-schnell', 'Flux Schnell (Fast)'),
        ('flux-dev', 'Flux Dev (High Quality)'),
        ('sdxl', 'Stable Diffusion XL'),
    ]
    default_image_model = models.CharField(
        "Модель для картинок", max_length=50, choices=IMAGE_MODEL_CHOICES, default='flux-schnell')

    # --- Авто-настройки ---
    auto_translate_languages = models.CharField(
        "Языки для авто-перевода", max_length=50, default="ru,de", help_text="Через запятую, например: ru,de,es")
    auto_generate_images = models.BooleanField(
        "Авто: Генерировать картинки после статьи", default=True)
    auto_generate_voice = models.BooleanField(
        "Авто: Генерировать озвучку", default=False)
    auto_assemble_video = models.BooleanField(
        "Авто: Монтировать видео в конце", default=False)

    class Meta:
        verbose_name = "Настройки системы"
        verbose_name_plural = "Настройки системы"

    def __str__(self):
        return "Глобальные настройки"

    @classmethod
    def get_config(cls):
        """Удобный метод: возвращает настройки или создает их, если нет."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class ArticleStructureTemplate(models.Model):
    """
    Шаблоны структуры статьи (Prompt Engineering для плана).
    Хранит инструкции, как строить сюжет: Hook -> Body -> Climax.
    """
    name = models.CharField("Название шаблона", max_length=100,
                            help_text="Например: 'Классический хук', 'Конспирология'")
    description = models.TextField("Описание", blank=True)

    # Сам промпт, который формирует план
    structure_prompt = models.TextField(
        "Промпт структуры",
        help_text="Инструкция для AI. Используй переменные {topic}, {angle}, {notes}."
    )

    is_active = models.BooleanField("Активен", default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Шаблон структуры статьи"
        verbose_name_plural = "Шаблоны структур статей"
