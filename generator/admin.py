from django.contrib import admin
from .models import VideoProject, MediaAsset


@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ('topic', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('topic', 'angle')

    # Делаем поля заметок большими и удобными
    fieldsets = (
        ('Основное', {
            'fields': ('topic', 'angle', 'notes')
        }),
        ('Статус и Файлы', {
            'fields': ('status', 'output_file')
        }),
    )


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('project', 'asset_type', 'order', 'created_at')
    list_filter = ('asset_type',)
