from django.contrib import admin

from .models import ShortProject, ShortScene


class ShortSceneInline(admin.TabularInline):
    model = ShortScene
    extra = 0


@admin.register(ShortProject)
class ShortProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "style", "provider", "status", "created_at")
    list_filter = ("style", "status", "provider")
    search_fields = ("topic", "hook", "voiceover")
    inlines = [ShortSceneInline]


@admin.register(ShortScene)
class ShortSceneAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "order", "duration")
    list_filter = ("duration",)
    search_fields = ("text", "image_prompt", "project__topic")
