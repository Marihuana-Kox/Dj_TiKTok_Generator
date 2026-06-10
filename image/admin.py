from django.contrib import admin
from django.db import models
from django.forms import TextInput
from django.utils.html import format_html
from .models import ImageProject, ImagePrompt


class ImagePromptInline(admin.StackedInline):  # 🔥 Изменили TabularInline на StackedInline
    """
    Позволяет редактировать кадры (сцены) вертикальными блоками прямо внутри проекта.
    """

    model = ImagePrompt
    extra = 0  # Не создавать пустые строки автоматически
    formfield_overrides = {
        models.ImageField: {
            "widget": TextInput(attrs={"style": "width: 80%; font-family: monospace;"})
        },
    }
    # Группируем поля внутри каждого кадра для максимального удобства
    fieldsets = [
        (
            "Кадр / Сцена",
            {"fields": (("order", "generation_status"), ("scene_description", "prompt_text"))},
        ),
        ("Результат генерации", {"fields": (("image", "image_preview"), "error_message")}),
    ]

    readonly_fields = ["image_preview"]
    ordering = ["order"]

    def image_preview(self, obj):
        """Выводит миниатюру картинки"""
        url = obj.smart_image_url
        if url:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 120px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" /></a>',
                url,
                url,
            )
        return "Нет изображения"

    image_preview.short_description = "Текущее превью"


@admin.register(ImageProject)
class ImageProjectAdmin(admin.ModelAdmin):
    """
    Настройка отображения самого проекта генерации картинок.
    """

    # Что отображать в общем списке проектов
    list_display = [
        "id",
        "title",
        "article",
        "style_preset",
        "aspect_ratio",
        "status",
        "prompts_count",
        "created_at",
    ]

    # Фильтры в правой колонке
    list_filter = ["status", "style_preset", "aspect_ratio", "created_at"]

    # Поля, по которым работает поиск
    search_fields = ["title", "search_title", "article__translations__title"]

    # Подключаем сцены внутрь проекта
    inlines = [ImagePromptInline]

    # Группируем поля на странице редактирования для красоты
    fieldsets = [
        ("Основная информация", {"fields": ("article", "title", "status", "search_title")}),
        (
            "Настройки AI Генерации",
            {"fields": ("style_preset", "custom_style_prompt", "aspect_ratio")},
        ),
        (
            "Состояние очереди",
            {
                "fields": ("prompts_generated", "images_generated"),
                "classes": ("collapse",),  # Свернуть этот блок по умолчанию
            },
        ),
    ]

    readonly_fields = ["search_title"]

    def prompts_count(self, obj):
        """Выводит количество сцен в проекте"""
        return obj.prompts.count()

    prompts_count.short_description = "Кол-во кадров"


@admin.register(ImagePrompt)
class ImagePromptAdmin(admin.ModelAdmin):
    """
    Отдельная админка для кадров на случай, если тебе понадобится
    найти конкретную сцену по всей базе независимо от проекта.
    """

    list_display = ["id", "project", "order", "image_preview", "generation_status"]
    list_filter = ["generation_status"]
    search_fields = ["prompt_text", "scene_description", "project__title"]
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        url = obj.smart_image_url
        if url:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 60px; border-radius: 4px;" /></a>',
                url,
                url,
            )
        return "—"

    image_preview.short_description = "Миниатюра"
