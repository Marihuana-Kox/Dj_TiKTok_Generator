from pyexpat import model
from django.db import models


class VideoProject(models.Model):
    STATUS_CHOICES = [
        ("pending", "В очереди"),
        ("processing", "Генерируется"),
        ("completed", "Готово"),
        ("failed", "Ошибка"),
    ]

    topic = models.CharField("Тема видео", max_length=255)
    angle = models.TextField(
        "Ракурс / Парадокс", help_text="Основная идея или технологический парадокс"
    )
    notes = models.TextField(
        "Заметки / Факты", help_text="Детальные факты, даты, имена, вопросы для исследования"
    )

    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default="pending")
    output_file = models.FileField("Готовое видео", upload_to="videos/", null=True, blank=True)
    idea_style = models.CharField("Код промпта", max_length=100, null=True, blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    def __str__(self):
        return f"{self.topic} ({self.status})"

    class Meta:
        verbose_name = "Идея"
        verbose_name_plural = "Идеи"
        ordering = ["-created_at"]


class ResearchProject(models.Model):
    """
    Новая модель для исследовательских данных в формате JSON.
    Не конфликтует со старой логикой VideoProject.
    """

    STATUS_CHOICES = [
        ("pending", "В очереди"),
        ("processing", "Генерируется"),
        ("completed", "Готово"),
        ("failed", "Ошибка"),
    ]

    # Базовые поля (дублируем для независимости)
    topic = models.CharField("Тема", max_length=255)
    provider = models.CharField("AI провайдер", max_length=50, default="openai")

    # 🔥 ГЛАВНОЕ ПОЛЕ: гибкий JSON для любых структур от AI
    research_data = models.JSONField(
        "Исследовательские данные (JSON)",
        default=dict,
        blank=True,
        help_text="Сырой JSON от AI: facts, scores, hooks, visual_moments...",
    )

    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField("Ошибка", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Исследование (JSON)"
        verbose_name_plural = "Исследования (JSON)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"🔍 {self.topic} ({self.status})"

    @property
    def facts_count(self):
        """Быстрый доступ к кол-ву фактов без парсинга"""
        return len(self.research_data.get("facts", []))

    @property
    def top_fact(self):
        """Возвращает факт с максимальным curiosity_score"""
        facts = self.research_data.get("facts", [])
        if not facts:
            return None
        return max(facts, key=lambda x: x.get("curiosity_score", 0))
