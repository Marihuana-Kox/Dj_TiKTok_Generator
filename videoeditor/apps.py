from django.apps import AppConfig


class VideoeditorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "videoeditor"
    # 🔥 ДОБАВЛЯЕМ ЭТУ СТРОКУ (перевод названия всего приложения в меню админки):
    verbose_name = "Видеостудия"
