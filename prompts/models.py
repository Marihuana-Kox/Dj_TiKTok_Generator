from django.db import models


class BasePrompt(models.Model):
    """Базовый класс для общих полей"""
    name = models.CharField("Название", max_length=100)
    code_name = models.SlugField(
        "Кодовое имя", unique=True, help_text="Уникальный ID для кода, например 'idea_facts_v1'")
    description = models.TextField(
        "Описание", blank=True, help_text="Для чего этот промпт? (на русском)")

    template_content = models.TextField(
        "Текст промпта (EN)", help_text="Шаблон на английском. Переменные: {topic}, {context}, {language} и т.д.")

    is_active = models.BooleanField("pending", default=True)
    version = models.CharField("Версия", max_length=20, default="1.0")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True  # Это абстрактный класс, он не создаст таблицу сам по себе

    def __str__(self):
        status = "✅" if self.is_active else "❌"
        return f"{status} [{self.code_name}] {self.name}"

    def render(self, **kwargs):
        try:
            # Добавляем язык по умолчанию, если не передан
            if 'language' not in kwargs:
                kwargs['language'] = 'Russian'
            return self.template_content.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable in prompt: {e}")

# --- ТАБЛИЦА 1: Промпты для ИДЕЙ ---


class IdeaPrompt(BasePrompt):
    STYLE_CHOICES = [
        ('facts', 'Факты и Вопросы'),
        ('sensational', 'Сенсационный/Кликбейт'),
        ('mystery', 'Загадки и Тайны'),
        ('educational', 'Образовательный/Строгий'),
    ]
    style = models.CharField(
        "Стиль подачи", max_length=50, choices=STYLE_CHOICES, default='facts')

    class Meta:
        verbose_name = "Промпт для Идеи"
        verbose_name_plural = "1. Промпты для Идей"
        ordering = ['-is_active', 'style']

# --- ТАБЛИЦА 2: Промпты для ПЛАНА/СТРУКТУРЫ ---


class StructurePlanPrompt(BasePrompt):
    """
    Промпты для генерации скелета статьи: Хук, Интрига, Факты, Вывод.
    Результатом будет JSON со структурой.
    """
    class Meta:
        verbose_name = "Промпт для Плана Статьи"
        verbose_name_plural = "2. Промпты для Планов (Структура)"
        ordering = ['-is_active', '-created_at']

# --- ТАБЛИЦА 3: Промпты для СТАТЕЙ ---


class ArticlePrompt(BasePrompt):
    """
    Промпты для написания полного текста статьи на основе плана.
    """
    # Связь с планом: Можно выбрать дефолтный план для этого промпта статьи
    # Но лучше выбирать их независимо при генерации.
    # Если нужна жесткая связка "Многие к одному" (одна статья использует один план),
    # то можно добавить поле ForeignKey, но гибче выбирать их парой в интерфейсе.
    # Пока оставим независимыми, а связь настроим в логике сервиса или через админку настроек.

    class Meta:
        verbose_name = "Промпт для Статьи"
        verbose_name_plural = "3. Промпты для Статей"
        ordering = ['-is_active', '-created_at']
