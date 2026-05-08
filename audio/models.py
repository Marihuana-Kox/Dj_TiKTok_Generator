from django.db import models
from django.contrib.auth.models import User
from article.models import Article  # Или твоя модель статьи


class AudioProject(models.Model):
    """Проект озвучки (аналог ImageProject)"""

    STATUS_CHOICES = [
        ('pending', '⏳ Ожидание'),
        ('processing', '🔄 В процессе'),
        ('completed', '✅ Готово'),
        ('failed', '❌ Ошибка'),
    ]

    # Связи
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='audio_projects')
    article = models.ForeignKey(Article, on_delete=models.CASCADE,
                                related_name='audio_projects', null=True, blank=True)

    # Настройки
    title = models.CharField("Название", max_length=200)
    provider = models.CharField(
        "Провайдер", max_length=50, default='replicate_f5tts')
    voice_preset = models.CharField("Голос", max_length=50, default='default')
    language = models.CharField("Язык", max_length=10, default='ru')

    # Статус
    status = models.CharField("Статус", max_length=20,
                              choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField("Ошибка", blank=True)

    # Аудиофайл (итоговый)
    audio_file = models.FileField(
        "Аудиофайл", upload_to='audio_projects/', null=True, blank=True)

    # Мета
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Аудио проект"
        verbose_name_plural = "Аудио проекты"
        ordering = ['-created_at']

    def __str__(self):
        return f"🎤 {self.title} ({self.status})"

    def get_duration(self):
        """Длительность аудио (если есть файл)"""
        if self.audio_file:
            # Можно добавить вычисление через mutagen
            return None
        return None


class AudioTrack(models.Model):
    """Отдельный аудиотрек (сцена/абзац)"""

    STATUS_CHOICES = [
        ('pending', '⏳ Ожидание'),
        ('processing', '🔄 Генерация'),
        ('success', '✅ Готово'),
        ('failed', '❌ Ошибка'),
    ]

    # Связи
    project = models.ForeignKey(
        AudioProject, on_delete=models.CASCADE, related_name='tracks')

    # Контент
    order = models.PositiveIntegerField("Порядок", default=0)
    text = models.TextField("Текст для озвучки")

    # Результат
    audio_file = models.FileField(
        "Аудиофайл", upload_to='audio_tracks/', null=True, blank=True)
    status = models.CharField("Статус", max_length=20,
                              choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField("Ошибка", blank=True)

    # Мета
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Аудиотрек"
        verbose_name_plural = "Аудиотреки"
        ordering = ['order']

    def __str__(self):
        return f"🎵 Трек #{self.order} ({self.status})"
