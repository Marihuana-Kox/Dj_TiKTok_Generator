from django.contrib import admin
from .models import IdeaPrompt, SystemInstruction, ArticlePrompt


@admin.register(IdeaPrompt)
class IdeaPromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'style', 'code_name',
                    'version', 'is_active', 'created_at')
    list_filter = ('style', 'is_active')
    search_fields = ('name', 'template_content')
    fieldsets = (
        ('Инфо', {'fields': ('name', 'code_name',
         'style', 'version', 'description')}),
        ('Промпт (EN)', {'fields': ('template_content',)}),
        ('Статус', {'fields': ('is_active',)}),
    )


@admin.register(SystemInstruction)
class SystemInstructionAdmin(admin.ModelAdmin):
    # Используем только существующие поля: name, code_name, is_active, version
    list_display = ('name', 'code_name', 'is_active', 'version', 'created_at')

    search_fields = ('name', 'code_name', 'template_content', 'description')
    list_filter = ('is_active',)

    # Группировка полей в форме редактирования
    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "code_name", "description", "is_active", "version")
        }),
        ("Шаблон промпта", {
            "fields": ("template_content",),
            # Можно свернуть в кучу, если текст длинный
            "classes": ("collapse",)
        }),
    )


@admin.register(ArticlePrompt)
class ArticlePromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_name', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)
    fieldsets = (
        ('Инфо', {'fields': ('name', 'code_name', 'version', 'description')}),
        ('Промпт (EN)', {'fields': ('template_content',)}),
        ('Статус', {'fields': ('is_active',)}),
    )
