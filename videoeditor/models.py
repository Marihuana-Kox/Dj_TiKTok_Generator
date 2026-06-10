import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta

from audio.models import AudioProject
from tiktok_web import settings


class ProjectVideoRelease(models.Model):
    STATUS_CHOICES = [
        ("rendering", "В процессе сборки"),
        ("ready", "Готово к скачиванию"),
        ("expired", "Файл видео удален (история сохранена)"),
        ("failed", "Ошибка генерации"),
    ]
    project = models.ForeignKey(
        AudioProject, on_delete=models.CASCADE, related_name="video_releases"
    )
    # project_id является уникальным первичным ключом (один проект — одна строка)
    # project_id = models.IntegerField(primary_key=True, verbose_name="ID проекта")
    pj_title = models.CharField(max_length=255, verbose_name="Название проекта")

    # pj_data — дата создания самого проекта (пишется один раз)
    pj_data = models.DateTimeField(default=timezone.now, verbose_name="Дата создания проекта")

    # video_created_at — дата сборки текущего клипа (меняется при каждом рендере)
    video_created_at = models.DateTimeField(auto_now=True, verbose_name="Дата сборки видео")

    # pj_datatime_clip — дата, когда текущий MP4-файл должен быть удален (текущий рендер + 10 дней)
    pj_datatime_clip = models.DateTimeField(verbose_name="Дата удаления файла")

    # pj_link — путь к актуальному скомпилированному MP4
    pj_link = models.FileField(
        upload_to="projects/videos/", null=True, blank=True, verbose_name="Файл видео"
    )

    # pj_status — текущий статус
    pj_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="rendering", verbose_name="Статус"
    )

    # pj_config — хранит историю из максимум 3-х конфигураций в виде списка JSON
    pj_config = models.JSONField(default=list, verbose_name="История конфигураций сценария")
    pj_current_config = models.JSONField(
        default=list, blank=True, verbose_name="Текущие рабочие настройки (черновик в редакторе)"
    )

    class Meta:
        verbose_name = "Готовый видеопроект"
        verbose_name_plural = "Готовые видеопроекты"

    def add_or_update_config(
        self, new_timeline_data=None, config_id_to_move_up=None, is_render=False
    ):
        """
        Управляет историей (pj_config) и текущим черновиком (pj_current_config).
        Ограничивает массив pj_config максимум 3 элементами ТОЛЬКО при реальном рендере.
        """
        current_history = self.pj_config
        if not isinstance(current_history, list):
            current_history = []

        # Вариант А: Восстановление старой конфигурации из истории
        if config_id_to_move_up:  # <-- Используем оригинальное имя из views.py
            for found_config in current_history:
                if (
                    found_config.get("config_id") == config_id_to_move_up
                ):  # <-- Используем оригинальное имя из views.py
                    self.pj_current_config = found_config.get("timeline_state", [])
                    return

        # Вариант Б: Прилетели данные таймлайна
        if new_timeline_data:
            # СИНХРОНИЗАЦИЯ ЧЕРНОВИКА: всегда сохраняем текущее состояние при любом изменении
            self.pj_current_config = new_timeline_data

            # В ИСТОРИЮ (pj_config) добавляем ТОЛЬКО если нажата кнопка рендера
            if is_render:
                new_config_entry = {
                    "config_id": str(uuid.uuid4())[:8],
                    "updated_at": timezone.now().isoformat(),
                    "scenes_count": len(new_timeline_data),
                    "timeline_state": new_timeline_data,
                }

                # Вставляем новую запись на самый верх истории
                current_history.insert(0, new_config_entry)

                # Держим лимит строго в 3 записи
                if len(current_history) > 3:
                    current_history = current_history[:3]

                self.pj_config = current_history

    def save(self, *args, **kwargs):
        # При каждой перезаписи/генерации сдвигаем жизнь видео на 10 дней вперед
        # Берём количество дней из настроек, если забыли указать — будет 10 по умолчанию
        storage_days = getattr(settings, "VIDEO_STORAGE_DAYS", 10)
        self.pj_datatime_clip = timezone.now() + timedelta(days=storage_days)
        super().save(*args, **kwargs)
