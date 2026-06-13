from django.db import models
from django.utils.text import slugify


class StoryPlan(models.Model):
    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("approved", "Утвержден"),
        ("script_generated", "Сценарий создан"),
        ("rejected", "Отклонен"),
    ]

    # 1. СВЯЗИ (Строковые ссылки предотвращают циклические импорты при запуске Django)
    cluster = models.ForeignKey(
        "article.ArticleCluster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="story_plans",
        help_text="Глобальная тема или ниша (опционально)",
    )
    research_project = models.ForeignKey(
        "topics.ResearchProject",
        on_delete=models.CASCADE,
        related_name="story_plans",
        help_text="Исходные исследовательские данные, на которых основан план",
    )

    # 2. ИДЕНТИФИКАЦИЯ
    title = models.CharField("Название сюжета", max_length=255)
    slug = models.SlugField("Слаг (URL)", max_length=255, unique=True, blank=True)

    # 3. ДАННЫЕ (Ядро)
    story_data = models.JSONField(
        "Структура сюжета (JSON)",
        default=dict,
        blank=True,
        help_text="Сырой JSON от Story Planner: hook, structure, selected_facts...",
    )

    # 4. ДЕНОРМАЛИЗАЦИЯ (Для молниеносных фильтров и сортировок без парсинга JSON)
    virality_score = models.PositiveSmallIntegerField("Вирусный потенциал (1-10)", default=0)
    narrative_style = models.CharField("Стиль повествования", max_length=50, blank=True)

    # 5. МЕТАДАННЫЕ
    provider = models.CharField("AI провайдер", max_length=50, default="openai")
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default="draft")

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Сюжетный план (Story Plan)"
        verbose_name_plural = "Сюжетные планы"
        ordering = ["-virality_score", "-created_at"]

    def __str__(self):
        return f"📖 {self.title} ({self.narrative_style}, Score: {self.virality_score})"

    def save(self, *args, **kwargs):
        # Автогенерация уникального слага при создании
        if not self.slug:
            base_slug = slugify(self.title)
            unique_slug = base_slug
            counter = 1
            while StoryPlan.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    # --- УДОБНЫЕ СВОЙСТВА (Properties) для отображения в админке и шаблонах ---
    @property
    def hook_text(self):
        """Быстрый доступ к тексту хука из JSON"""
        return self.story_data.get("hook_fact", {}).get("fact", "Хук не указан")

    @property
    def selected_facts_count(self):
        """Количество отобранных фактов для сценария"""
        return len(self.story_data.get("selected_facts", []))

    @property
    def climax_text(self):
        """Текст кульминации из JSON"""
        return self.story_data.get("story_structure", {}).get("climax", "Кульминация не указана")
