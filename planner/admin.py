from django.contrib import admin
from .models import StoryPlan


@admin.register(StoryPlan)
class StoryPlanAdmin(admin.ModelAdmin):
    # Что показывать в списке
    list_display = ("title", "cluster", "narrative_style", "virality_score", "status", "created_at")

    # Фильтры в правой панели
    list_filter = ("status", "narrative_style", "cluster", "provider")

    # Поиск по обычным полям и внутри JSON-структуры (требует PostgreSQL для вложенных ключей)
    search_fields = ("title", "story_data__central_mystery", "story_data__hook_fact__fact")

    # Автозаполнение слага при вводе названия
    prepopulated_fields = {"slug": ("title",)}

    # Поля, которые нельзя редактировать вручную
    readonly_fields = (
        "created_at",
        "updated_at",
        "selected_facts_count",
        "hook_text",
        "climax_text",
    )

    # Логическая группировка полей в форме редактирования
    fieldsets = (
        ("Основное", {"fields": ("title", "slug", "cluster", "research_project", "status")}),
        ("Аналитика", {"fields": ("virality_score", "narrative_style", "provider")}),
        (
            "Быстрый просмотр содержимого",
            {
                "fields": ("hook_text", "climax_text", "selected_facts_count"),
                "classes": ("collapse",),  # Скрыто по умолчанию для экономии места
                "description": "Извлеченные данные из JSON для быстрой оценки качества плана.",
            },
        ),
        (
            "Сырые данные JSON",
            {
                "fields": ("story_data",),
                "classes": ("collapse",),
                "description": "Полный ответ от LLM. Редактируйте с осторожностью.",
            },
        ),
        (
            "Системные метаданные",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
