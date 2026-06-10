from django.contrib import admin
from .models import ProjectVideoRelease


@admin.register(ProjectVideoRelease)
class ProjectVideoReleaseAdmin(admin.ModelAdmin):
    # Столбцы, которые будут видны в списке всех записей
    list_display = ("pj_title", "pj_status", "pj_datatime_clip")

    # Фильтры в правой колонке
    list_filter = ("pj_status",)

    readonly_fields = ("project_id", "project", "video_created_at")
    # Поля, по которым можно искать (например, по ID проекта)
    search_fields = ("pj_title", "project_id", "project__title")

    # Группировка полей внутри формы редактирования/создания
    fieldsets = (
        ("Связь и Настройки", {"fields": ("project_id",)}),
        ("Статус и Ссылки", {"fields": ("pj_status", "pj_link", "pj_datatime_clip")}),
        (
            "Данные конфигураций (JSON)",
            {
                "fields": ("pj_config", "pj_current_config"),
                "description": (
                    "Сюда записывается массив из максимум 3-х конфигураций сценария",
                    "Сюда записывается массив текущего сценария конфигурации",
                ),
            },
        ),
    )

    # Кастомный метод, чтобы вывести имя владельца аудио-проекта в список (для удобства)
    @admin.display(description="Пользователь")
    def get_project_user(self, obj):
        return obj.project.user.username if obj.project and obj.project.user else "-"

    class Meta:
        verbose_name = "Готовый видеопроект"
        verbose_name_plural = "Готовые видеопроекты"

    def __str__(self):
        return f"Название проекта {self.pj_title}"
