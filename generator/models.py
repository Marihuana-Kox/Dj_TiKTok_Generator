from django.db import models
from topics.models import VideoProject


class MediaAsset(models.Model):
    TYPE_CHOICES = [
        ('image', 'Изображение'),
        ('audio', 'Аудио'),
        ('script', 'Текст сценария'),
    ]

    project = models.ForeignKey(
        VideoProject, on_delete=models.CASCADE, related_name='assets')
    asset_type = models.CharField("Тип", max_length=10, choices=TYPE_CHOICES)
    file = models.FileField(
        "Файл", upload_to='assets/%Y/%m/%d/', null=True, blank=True)
    content_text = models.TextField("Текстовое содержание", blank=True)
    prompt_used = models.TextField("Промпт", blank=True)
    order = models.IntegerField("Порядок", default=0)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    def __str__(self):
        return f"{self.asset_type} для {self.project.topic}"

    class Meta:
        verbose_name = "Медиафайл"            # Название в единственном числе
        verbose_name_plural = "Медиафайлы"    # Название во множественном числе


class ScriptData(models.Model):
    """
    Хранит сгенерированные тексты: сценарий на EN, переводы, заголовок, хэштеги.
    Связь один-к-одному с проектом.
    """
    project = models.OneToOneField(
        VideoProject, on_delete=models.CASCADE, related_name='script_data')

    script_full = models.TextField(
        "Полный сценарий (EN)", blank=True, default="")
    script_ru = models.TextField("Перевод RU", blank=True, default="")
    script_de = models.TextField("Перевод DE", blank=True, default="")

    title = models.CharField(
        "Заголовок видео", max_length=255, blank=True, default="")
    hashtags = models.TextField("Хэштеги", blank=True, default="")
    scene_breakdown = models.JSONField(
        "Разбивка на сцены", default=list, blank=True)
    # Пример данных: [{"title": "Hook", "text": "..."}, {"title": "Fact 1", "text": "..."}]
    # Можно хранить дополнительные данные в JSON (например, исходные промпты)
    metadata = models.JSONField("Доп. данные", default=dict, blank=True)

    def __str__(self):
        return f"Сценарий для {self.project.topic}"

    class Meta:
        verbose_name = "Данные сценария"
        verbose_name_plural = "Данные сценариев"
