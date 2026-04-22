from django.db import models
from generator.models import VideoProject  # Связь с проектом


class ImagePrompt(models.Model):
    ASPECT_RATIOS = [
        ('9:16', 'Vertical (9:16) - TikTok/Reels'),
        ('16:9', 'Horizontal (16:9) - YouTube'),
        ('1:1', 'Square (1:1) - Post'),
        ('4:3', 'Classic (4:3)'),
    ]

    project = models.ForeignKey(
        VideoProject, on_delete=models.CASCADE, related_name='image_prompts')

    prompt_text = models.TextField("Текст промпта")
    aspect_ratio = models.CharField(
        "Размер", max_length=10, choices=ASPECT_RATIOS, default='9:16')

    order = models.IntegerField("Порядок", default=0)
    is_generated = models.BooleanField("Картинка создана", default=False)

    # Связь с готовым файлом картинки (если сгенерировано)
    generated_image = models.ImageField(
        "Готовая картинка", upload_to='images/%Y/%m/', blank=True, null=True)

    def __str__(self):
        return f"Prompt {self.order} for {self.project.topic}"

    class Meta:
        ordering = ['order']
        verbose_name = "Промпт для картинки"
        verbose_name_plural = "Промпты для картинок"
