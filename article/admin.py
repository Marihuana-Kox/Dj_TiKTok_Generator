from django.contrib import admin
from .models import Article, ArticleCluster, ArticleTranslation, ImagePrompt, Language, SceneType

# 1. Админка для Языков и Типов сцен (справочники)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'flag_emoji', 'is_active')
    list_filter = ('is_active',)


@admin.register(ArticleCluster)
class ArticleClusterAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_idea', 'is_complete', 'created_at')
    # Можно добавить inline для переводов, если нужно редактировать их прямо здесь
    filter_horizontal = ()


@admin.register(ArticleTranslation)
class ArticleTranslationAdmin(admin.ModelAdmin):
    list_display = ('id', 'cluster', 'language', 'title', 'status')
    list_filter = ('language', 'status', 'cluster__is_complete')
    search_fields = ('title', 'content')

# 5. Админка для Основных Статей (Article)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_at')
    list_filter = ('status',)
    # Добавляем Inline, чтобы видеть промпты прямо внутри статьи
    inlines = []  # Если хочешь видеть промпты внутри статьи, раскомментируй класс ниже и добавь ImagePromptInline сюда
