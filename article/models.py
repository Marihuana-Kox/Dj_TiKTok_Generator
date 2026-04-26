from django.db import models


class Language(models.Model):
    code = models.CharField("Код", max_length=5,
                            unique=True, help_text="en, ru, de...")
    name = models.CharField("Название", max_length=50)
    flag_emoji = models.CharField("Флаг", max_length=5, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Язык"
        verbose_name_plural = "1. Языки"

    def __str__(self):
        return f"{self.flag_emoji} {self.name} ({self.code})"


class SceneType(models.Model):
    code = models.CharField("Код", max_length=50, unique=True)
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание задачи", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Тип сцены"
        verbose_name_plural = "2. Типы сцен"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Article(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('in_progress', 'В работе'),
        ('published', 'Опубликовано'),
    ]
    language = models.ForeignKey(
        Language, on_delete=models.PROTECT, null=True, blank=True, related_name='articles')
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
        lang_name = self.language.name if self.language else "Unknown"
        return f"[{lang_name}] {self.title}"

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи (Одиночные)"
        ordering = ['-created_at']


class ArticleCluster(models.Model):
    source_idea = models.ForeignKey('topics.VideoProject', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='article_clusters')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_complete = models.BooleanField(default=False)

    def __str__(self):
        # Ищем русский или первый попавшийся
        main_trans = self.translations.filter(language__code='ru').first()
        if not main_trans:
            main_trans = self.translations.first()
        title = main_trans.title if main_trans else f"Cluster #{self.id}"
        return f"📄 {title}"

    class Meta:
        verbose_name = "Статья (Кластер)"
        verbose_name_plural = "Управление статьями (Кластеры)"
        ordering = ['-created_at']


class ArticleTranslation(models.Model):
    cluster = models.ForeignKey(
        ArticleCluster, on_delete=models.CASCADE, related_name='translations')
    # Теперь связь с таблицей языков, а не choices
    language = models.ForeignKey(
        Language, on_delete=models.PROTECT, related_name='article_translations')

    title = models.CharField("Заголовок", max_length=255)
    description = models.TextField("Описание (SEO)", blank=True)
    content = models.TextField("Текст статьи")
    hashtags = models.CharField("Хештеги", max_length=255, blank=True)

    status = models.CharField("Статус", max_length=20, default='draft', choices=[
        ('draft', 'Черновик'),
        ('review', 'На проверке'),
        ('published', 'Опубликовано'),
        ('rejected', 'Отклонено'),
    ])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.language}] {self.title}"

    class Meta:
        verbose_name = "Перевод статьи"
        verbose_name_plural = "Переводы статей"
        unique_together = ('cluster', 'language')
        ordering = ['language__order']


class ImagePrompt(models.Model):
    # Связь со статьей (одна статья -> много промптов)
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name='image_prompts')

    # Связь с типом сцены из справочника
    scene_type = models.ForeignKey(
        SceneType, on_delete=models.PROTECT, related_name='prompts')

    prompt_text = models.TextField("Промпт (EN)")
    image_url = models.URLField("URL картинки", blank=True, null=True)
    is_generated = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Промпт изображения"
        verbose_name_plural = "3. Промпты изображений"
        ordering = ['scene_type__order']

    def __str__(self):
        return f"Prompt: {self.scene_type} for {self.article.title}"
