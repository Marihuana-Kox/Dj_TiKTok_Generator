from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('title', 'content')
