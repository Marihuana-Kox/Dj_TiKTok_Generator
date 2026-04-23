from django.db import models


class VideoProject(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В очереди'),
        ('processing', 'Генерируется'),
        ('completed', 'Готово'),
        ('failed', 'Ошибка'),
    ]

    topic = models.CharField("Тема видео", max_length=255)
    angle = models.TextField(
        "Ракурс / Парадокс", help_text="Основная идея или технологический парадокс")
    notes = models.TextField(
        "Заметки / Факты", help_text="Детальные факты, даты, имена, вопросы для исследования")

    status = models.CharField("Статус", max_length=20,
                              choices=STATUS_CHOICES, default='pending')
    output_file = models.FileField(
        "Готовое видео", upload_to='videos/', null=True, blank=True)

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    def __str__(self):
        return f"{self.topic} ({self.status})"

    class Meta:
        verbose_name = "Идея"
        verbose_name_plural = "Идеи"
        ordering = ['-created_at']
