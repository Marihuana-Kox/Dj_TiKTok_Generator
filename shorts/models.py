from django.db import models


class ShortProject(models.Model):
    STYLE_DOCUMENTARY = "DOCUMENTARY"
    STYLE_SHOCK = "SHOCK"
    STYLE_THEORY = "THEORY"

    STYLE_CHOICES = [
        (STYLE_DOCUMENTARY, "Documentary"),
        (STYLE_SHOCK, "Shock"),
        (STYLE_THEORY, "Theory"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PROCESSING = "processing"
    STATUS_SCRIPT_READY = "script_ready"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Черновик"),
        (STATUS_PROCESSING, "Генерация"),
        (STATUS_SCRIPT_READY, "Сценарий готов"),
        (STATUS_FAILED, "Ошибка"),
    ]

    topic = models.CharField("Тема", max_length=255)
    provider = models.CharField("AI провайдер", max_length=50)
    style = models.CharField("Выбранный стиль", max_length=20, choices=STYLE_CHOICES, blank=True)
    hook = models.TextField("Hook", blank=True)
    voiceover = models.TextField("Текст озвучки", blank=True)
    raw_response = models.JSONField("Сырой ответ AI", default=dict, blank=True)
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    error_message = models.TextField("Ошибка", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "TikTok сценарий"
        verbose_name_plural = "TikTok сценарии"
        ordering = ["-created_at"]

    def __str__(self):
        style = self.style or "no-style"
        return f"{self.topic} ({style})"


class ShortScene(models.Model):
    project = models.ForeignKey(ShortProject, on_delete=models.CASCADE, related_name="scenes")
    order = models.PositiveIntegerField("Порядок", default=1)
    text = models.TextField("Текст сцены")
    image_prompt = models.TextField("Промпт картинки")
    duration = models.PositiveIntegerField("Длительность, сек", default=3)

    class Meta:
        verbose_name = "Сцена TikTok"
        verbose_name_plural = "Сцены TikTok"
        ordering = ["order"]
        unique_together = ("project", "order")

    def __str__(self):
        return f"{self.project_id}: scene {self.order}"
