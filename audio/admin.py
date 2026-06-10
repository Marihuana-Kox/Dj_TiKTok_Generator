from django.contrib import admin
from .models import AudioProject, AudioTrack


@admin.register(AudioProject)
class AudioProjectAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "user", "status", "provider", "created_at"]
    list_filter = ["status", "provider", "language"]
    search_fields = ["title", "user__username"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AudioTrack)
class AudioTrackAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "order", "status", "created_at"]
    list_filter = ["status", "project"]
    search_fields = ["text", "project__title"]
