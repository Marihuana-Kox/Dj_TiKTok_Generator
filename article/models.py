from django.db import models


class Article(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('in_progress', 'В работе'),
        ('published', 'Опубликовано'),
    ]

    title = models.CharField("Заголовок", max_length=200)
    # Связь с идеей (опционально, если нужно)
    # idea = models.ForeignKey('topics.VideoProject', null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField(
        "Описание (Description)", blank=True, help_text="Краткое описание для превью (SEO)")
    # ... даты ...
    content = models.TextField("Текст статьи", blank=True)
    hashtags = models.CharField("Хештеги", max_length=255, blank=True,
                                help_text="5 хештегов через пробел, например: #история #тайны")
    # Или разбито на поля: intro, body, conclusion - адаптируй форму под себя

    status = models.CharField("Статус", max_length=20,
                              choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
