from django.contrib import admin
from .models import IdeaPrompt, ImagePromptTemplate, ScriptPrompt, SystemInstruction, ArticlePrompt


@admin.register(IdeaPrompt)
class IdeaPromptAdmin(admin.ModelAdmin):
    list_display = ("name", "style", "code_name", "version", "is_active", "created_at")
    list_filter = ("style", "is_active")
    search_fields = ("name", "template_content")
    fieldsets = (
        ("Инфо", {"fields": ("name", "code_name", "style", "version", "description")}),
        ("Промпт (EN)", {"fields": ("template_content",)}),
        ("Статус", {"fields": ("is_active",)}),
    )


@admin.register(SystemInstruction)
class SystemInstructionAdmin(admin.ModelAdmin):
    # Используем только существующие поля: name, code_name, is_active, version
    list_display = ("name", "code_name", "is_active", "version", "created_at")

    search_fields = ("name", "code_name", "template_content", "description")
    list_filter = ("is_active",)

    # Группировка полей в форме редактирования
    fieldsets = (
        (
            "Основная информация",
            {"fields": ("name", "code_name", "description", "is_active", "version")},
        ),
        (
            "Шаблон промпта",
            {
                "fields": ("template_content",),
                # Можно свернуть в кучу, если текст длинный
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ArticlePrompt)
class ArticlePromptAdmin(admin.ModelAdmin):
    list_display = ("name", "code_name", "version", "is_active", "created_at")
    list_filter = ("is_active",)
    fieldsets = (
        ("Инфо", {"fields": ("name", "code_name", "version", "description")}),
        ("Промпт (EN)", {"fields": ("template_content",)}),
        ("Статус", {"fields": ("is_active",)}),
    )


@admin.register(ImagePromptTemplate)
class ImagePromptTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "code_name", "preferred_format", "is_active", "version")
    list_filter = ("is_active", "preferred_format")
    search_fields = ("name", "code_name", "description")

    # ГРУППИРОВКА В МЕНЮ
    # Эта строка создает заголовок раздела в админке
    verbose_name = "Шаблон для Изображений"
    verbose_name_plural = "4. Промпты для Изображений"

    # Дополнительные настройки отображения полей
    fieldsets = (
        ("Основное", {"fields": ("name", "code_name", "description", "is_active", "version")}),
        (
            "Контент промпта",
            {
                "fields": ("template_content",),
                "description": "Используй переменные: {scenes_count}, {style_keywords}, {aspect_ratio}, {source_text}",
            },
        ),
        (
            "Настройки вывода",
            {
                "fields": ("preferred_format",),
            },
        ),
    )


@admin.register(ScriptPrompt)
class ScriptPromptAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    list_filter = ("is_active", "code")
    search_fields = ("name", "code")
    readonly_fields = ("updated_at",)
    fieldsets = (
        ("Основное", {"fields": ("code", "name", "is_active")}),
        ("Контент", {"fields": ("prompt_text",)}),
        ("Настройки", {"fields": ("config",), "classes": ("collapse",)}),
        ("Мета", {"fields": ("updated_at",)}),
    )
    # Эта строка создает заголовок раздела в админке
    verbose_name = "Промт для Сценариев"
    verbose_name_plural = "5. Промпты для Сценариев"
