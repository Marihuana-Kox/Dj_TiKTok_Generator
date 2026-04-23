from django.contrib import admin
from .models import IdeaPrompt, StructurePlanPrompt, ArticlePrompt


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


@admin.register(StructurePlanPrompt)
class StructurePlanPromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_name', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)
    fieldsets = (
        ('Инфо', {'fields': ('name', 'code_name', 'version', 'description')}),
        ('Промпт (EN)', {'fields': ('template_content',)}),
        ('Статус', {'fields': ('is_active',)}),
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
