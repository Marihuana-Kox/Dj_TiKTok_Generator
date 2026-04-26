from django.contrib import admin
from .models import Article, ArticleCluster, ArticleTranslation, ImagePrompt, Language, SceneType

# 1. Админка для Языков и Типов сцен (справочники)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'flag_emoji', 'is_active')
    list_filter = ('is_active',)


@admin.register(SceneType)
class SceneTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')

# 2. Админка для Промптов Изображений (ГЛАВНОЕ)


@admin.register(ImagePrompt)
class ImagePromptAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_article_title', 'scene_type',
                    'is_generated', 'prompt_short')
    list_filter = ('is_generated', 'scene_type', 'article__status')
    search_fields = ('prompt_text', 'article__title')
    readonly_fields = ('article', 'scene_type', 'prompt_text', 'image_url')

    def get_article_title(self, obj):
        return obj.article.title if obj.article else "-"
    get_article_title.short_description = "Статья"

    def prompt_short(self, obj):
        return f"{obj.prompt_text[:50]}..." if obj.prompt_text else "-"
    prompt_short.short_description = "Текст промпта"

# 3. Админка для Кластеров (Группы статей)


@admin.register(ArticleCluster)
class ArticleClusterAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_idea', 'is_complete', 'created_at')
    # Можно добавить inline для переводов, если нужно редактировать их прямо здесь
    filter_horizontal = ()

# 4. Админка для Переводов (Статьи на конкретных языках)


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

# --- ОПЦИОНАЛЬНО: Показывать промпты внутри статьи ---


class ImagePromptInline(admin.TabularInline):
    model = ImagePrompt
    extra = 0
    fields = ('scene_type', 'prompt_text', 'is_generated', 'image_url')
    readonly_fields = fields


# Чтобы включить это, добавь:
ArticleAdmin.inlines = [ImagePromptInline]
