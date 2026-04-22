from django.contrib import admin
from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('project', 'asset_type', 'order', 'created_at')
    list_filter = ('asset_type',)
