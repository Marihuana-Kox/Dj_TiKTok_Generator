import json

from django.contrib import admin
from django import forms
from django.contrib import messages
from django.utils.html import format_html
from django.urls import path
from django.utils.text import Truncator
from django.db import models
from django_json_widget.widgets import JSONEditorWidget
from django.shortcuts import render, redirect
from .models import ResearchProject, VideoProject
from .services import generate_unique_ideas


class GenerateIdeasForm(forms.Form):
    topic = forms.CharField(
        label="Тема для генерации",
        max_length=100,
        initial="История",
        widget=forms.TextInput(attrs={"class": "vTextField", "style": "width: 300px;"}),
    )
    count = forms.IntegerField(
        label="Количество идей",
        min_value=1,
        max_value=10,
        initial=3,
        widget=forms.NumberInput(attrs={"class": "vIntegerField", "style": "width: 60px;"}),
    )


class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "title_preview", "status", "created_at", "has_assets_count")
    readonly_fields = ("idea_style", "created_at", "updated_at")
    list_filter = ("status", "topic", "created_at")
    search_fields = ("topic", "angle", "notes")
    list_editable = ("status",)
    ordering = ("-created_at",)

    def title_preview(self, obj):
        text = obj.angle if obj.angle else obj.topic
        return text[:50] + "..." if len(text) > 50 else text

    title_preview.short_description = "Идея / Угол"

    def has_assets_count(self, obj):
        # Так как MediaAsset в другом приложении, используем related_name если он настроен,
        # или просто считаем через фильтр, если связь есть.
        # Если связи нет или она сложная, покажем заглушку или попробуем получить через reverse relation.
        # Предположим, что related_name='assets' настроен в модели MediaAsset (даже если она в generator).
        try:
            count = obj.assets.count()
            color = "green" if count > 0 else "gray"
            return format_html('<span style="color: {};">{} файлов</span>', color, count)
        except:
            # Если related_name не работает или модели нет в контексте
            return format_html('<span style="color: gray;">-</span>')

    has_assets_count.short_description = "Медиа"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "generate-ideas/",
                self.admin_site.admin_view(self.generate_ideas_view),
                name="topics_videoproject_generate",
            ),
        ]
        return custom_urls + urls

    def generate_ideas_view(self, request):
        if request.method == "POST":
            form = GenerateIdeasForm(request.POST)
            if form.is_valid():
                topic = form.cleaned_data["topic"]
                count = form.cleaned_data["count"]
                try:
                    created_count = generate_unique_ideas(count=count, topic=topic)
                    self.message_user(
                        request,
                        f"✅ Успешно сгенерировано и сохранено {created_count} новых идей по теме '{topic}'!",
                        level=messages.SUCCESS,
                    )
                    return redirect("admin:topics_videoproject_changelist")
                except Exception as e:
                    self.message_user(
                        request, f"❌ Ошибка генерации: {str(e)}", level=messages.ERROR
                    )
        else:
            form = GenerateIdeasForm()

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Генерация новых идей",
                "form": form,
                "opts": self.model._meta,
            }
        )
        return render(request, "admin/topics/generate_ideas.html", context)


@admin.register(ResearchProject)
class ResearchProjectAdmin(admin.ModelAdmin):
    list_display = ("topic", "status", "cluster", "facts_count", "created_at")
    list_filter = (
        "status",
        "cluster",
        "provider",
        "research_data",
    )
    search_fields = ("topic", "central_mystery")
    readonly_fields = ("created_at", "updated_at")

    formfield_overrides = {
        models.JSONField: {"widget": JSONEditorWidget},
    }

    def research_data_short(self, obj):
        return Truncator(str(obj.research_data)).chars(100)


# Регистрируем только VideoProject
admin.site.register(VideoProject, VideoProjectAdmin)
