import os
import uuid
from django.db import models
from article.models import ArticleCluster


def upload_to(instance, filename):
    # Сохраняем в папку: media/images/project_<ID>/<filename>
    return f"images/project_{instance.project.id}/{filename}"


class ImageProject(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('prompts_ready', 'Промпты готовы'),
        ('processing', 'Генерация изображений...'),
        ('completed', 'Готово'),
        ('failed', 'Ошибка'),
    ]

    STYLE_CHOICES = [
        ('cinematic', 'Cinematic Dark (Кино)'),
        ('realistic', 'Photorealistic (Фото)'),
        ('anime', 'Anime Style'),
        ('oil_painting', 'Oil Painting'),
        ('cyberpunk', 'Cyberpunk'),
        ('custom', 'Свой стиль...'),
    ]

    article = models.ForeignKey(
        ArticleCluster, on_delete=models.CASCADE, related_name='image_projects')
    title = models.CharField("Название проекта", max_length=200, blank=True)

    # Настройки
    style_preset = models.CharField(
        "Стиль", max_length=50, choices=STYLE_CHOICES, default='cinematic')
    custom_style_prompt = models.TextField(
        "Доп. описание стиля", blank=True, help_text="Например: '8k, highly detailed, dramatic lighting'")
    aspect_ratio = models.CharField("Формат", max_length=10, default='9:16', choices=[(
        '16:9', '16:9 (YouTube)'), ('9:16', '9:16 (TikTok)'), ('1:1', '1:1 (Post)')])

    status = models.CharField("Статус", max_length=20,
                              choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Флаги состояния всего проекта
    prompts_generated = models.BooleanField("Промпты созданы", default=False)
    images_generated = models.BooleanField("Картинки созданы", default=False)

    # Для поиска
    search_title = models.CharField(
        "Поисковый заголовок", max_length=200, blank=True, db_index=True)

    def save(self, *args, **kwargs):
        # Заполняем заголовок из статьи при сохранении проекта
        if self.article and self.article.translations.exists():
            ru = self.article.translations.filter(language__code='ru').first()
            self.search_title = ru.title if ru else self.article.translations.first().title
        super().save(*args, **kwargs)

    def reset_prompts(self):
        """Сбрасывает проект и удаляет все промпты"""
        self.prompts_generated = False
        self.images_generated = False
        self.status = 'draft'
        self.prompts.all().delete()  # Удаляем все связанные промпты
        self.save()

    def __str__(self):
        return f"Project {self.id} for {self.article}"

    def get_style_full(self):
        """Собирает полный промпт стиля"""
        base = self.custom_style_prompt if self.custom_style_prompt else ""
        if self.style_preset == 'cinematic':
            base += ", cinematic lighting, dramatic atmosphere, 8k, highly detailed, movie still"
        elif self.style_preset == 'realistic':
            base += ", photorealistic, 8k, raw photo, shot on 35mm lens"
        # ... можно добавить другие пресеты
        return base.strip(", ")


class ImagePrompt(models.Model):
    """Отдельный кадр/сцена внутри проекта"""

    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('generating', 'В процессе'),
        ('success', 'Успех'),
        ('failed', 'Ошибка'),
    ]

    # Связь с проектом (это единственная связь с "внешним миром")
    project = models.ForeignKey(
        ImageProject,
        on_delete=models.CASCADE,
        related_name='prompts'
    )

    # Порядок сцены (1, 2, 3...)
    order = models.IntegerField("Порядок сцены", default=0)

    # --- КОНТЕНТ ---
    scene_description = models.TextField(
        "Описание сцены (для человека)",
        help_text="Что происходит в кадре",
        blank=True
    )
    prompt_text = models.TextField(
        "Текст промпта (для AI)",
        help_text="На английском языке"
    )

    # --- РЕЗУЛЬТАТ ---
    image = models.ImageField(
        "Изображение",
        upload_to=upload_to,
        blank=True,
        null=True
    )
    generation_status = models.CharField(
        "Статус генерации",
        max_length=20,
        default='pending',
        choices=STATUS_CHOICES
    )
    error_message = models.TextField("Ошибка", blank=True)

    class Meta:
        ordering = ['order']  # Всегда сортировать по порядку

    def __str__(self):
        return f"Scene {self.order} - Project {self.project.id}"
