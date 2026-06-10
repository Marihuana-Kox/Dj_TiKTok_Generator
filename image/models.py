import os
import re
import uuid
from django.db import models
from article.models import ArticleCluster
from tiktok_web import settings


# 🔥 ДОБАВЛЯЕМ ТРАНСЛИТЕРАЦИЮ В ФАЙЛ МОДЕЛЕЙ
def transliterate(text: str) -> str:
    """Переводит кириллицу в безопасную латиницу для путей"""
    cyrillic = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    latin = [
        "a",
        "b",
        "v",
        "g",
        "d",
        "e",
        "yo",
        "zh",
        "z",
        "i",
        "y",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "r",
        "s",
        "t",
        "u",
        "f",
        "kh",
        "ts",
        "ch",
        "sh",
        "shch",
        "",
        "y",
        "",
        "e",
        "yu",
        "ya",
    ]
    tr_dict = dict(zip(cyrillic, latin))
    text = text.lower()
    return "".join(tr_dict.get(char, char) for char in text)


def upload_to(instance, filename):
    # 🔥 ИСПРАВЛЕНО: Теперь Django при генерации картинки СРАЗУ запишет в БД правильный латинский путь!
    project_title = instance.project.title or f"project_{instance.project.id}"

    safe_title = transliterate(project_title)
    clean_title = re.sub(r'[\\/*?:"<>| ]', "_", safe_title)
    clean_title = re.sub(r"_+", "_", clean_title).strip("_")
    folder_name = clean_title[:100]

    # Формируем имя файла на основе порядка сцены (как у тебя в smart_image_url)
    ext = os.path.splitext(filename)[1] or ".png"
    new_filename = f"pic_{instance.order}{ext}"

    # Возвращает: projects/moya_statya/pic_1.png
    return f"projects/{folder_name}/{new_filename}"


class ImageProject(models.Model):
    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("prompts_ready", "Промпты готовы"),
        ("processing", "Генерация изображений..."),
        ("completed", "Готово"),
        ("failed", "Ошибка"),
    ]

    STYLE_CHOICES = [
        ("cinematic", "Cinematic Dark (Кино)"),
        ("realistic", "Photorealistic (Фото)"),
        ("anime", "Anime Style"),
        ("oil_painting", "Oil Painting"),
        ("cyberpunk", "Cyberpunk"),
        ("custom", "Свой стиль..."),
    ]

    article = models.ForeignKey(
        ArticleCluster, on_delete=models.CASCADE, related_name="image_projects"
    )
    title = models.CharField("Название проекта", max_length=200, blank=True)

    # Настройки
    style_preset = models.CharField(
        "Стиль", max_length=50, choices=STYLE_CHOICES, default="cinematic"
    )
    custom_style_prompt = models.TextField(
        "Доп. описание стиля",
        blank=True,
        help_text="Например: '8k, highly detailed, dramatic lighting'",
    )
    aspect_ratio = models.CharField(
        "Формат",
        max_length=10,
        default="9:16",
        choices=[
            ("16:9", "16:9 (YouTube)"),
            ("9:16", "9:16 (TikTok)"),
            ("1:1", "1:1 (Post)"),
        ],
    )

    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Флаги состояния всего проекта
    prompts_generated = models.BooleanField("Промпты созданы", default=False)
    images_generated = models.BooleanField("Картинки созданы", default=False)

    # Для поиска
    search_title = models.CharField(
        "Поисковый заголовок", max_length=200, blank=True, db_index=True
    )

    class Meta:
        verbose_name = "Проект картинки"
        verbose_name_plural = "Проекты картинок"

    def save(self, *args, **kwargs):
        # Заполняем заголовок из статьи при сохранении проекта
        if self.article and self.article.translations.exists():
            ru = self.article.translations.filter(language__code="ru").first()
            self.search_title = ru.title if ru else self.article.translations.first().title
        super().save(*args, **kwargs)

    def reset_prompts(self):
        """Сбрасывает проект и удаляет все промпты"""
        self.prompts_generated = False
        self.images_generated = False
        self.status = "draft"
        self.prompts.all().delete()  # Удаляем все связанные промпты
        self.save()

    def __str__(self):
        return f"Project {self.id} for {self.article}"

    def get_style_full(self):
        """Собирает полный промпт стиля"""
        base = self.custom_style_prompt if self.custom_style_prompt else ""
        if self.style_preset == "cinematic":
            base += ", cinematic lighting, dramatic atmosphere, 8k, highly detailed, movie still"
        elif self.style_preset == "realistic":
            base += ", photorealistic, 8k, raw photo, shot on 35mm lens"
        # ... можно добавить другие пресеты
        return base.strip(", ")


class ImagePrompt(models.Model):
    """Отдельный кадр/сцена внутри проекта"""

    STATUS_CHOICES = [
        ("pending", "Ожидание"),
        ("generating", "В процессе"),
        ("success", "Успех"),
        ("failed", "Ошибка"),
    ]

    # Связь с проектом (это единственная связь с "внешним миром")
    project = models.ForeignKey(ImageProject, on_delete=models.CASCADE, related_name="prompts")

    # Порядок сцены (1, 2, 3...)
    order = models.IntegerField("Порядок сцены", default=0)

    # --- КОНТЕНТ ---
    scene_description = models.TextField(
        "Описание сцены (для человека)", help_text="Что происходит в кадре", blank=True
    )
    prompt_text = models.TextField("Текст промпта (для AI)", help_text="На английском языке")

    # --- РЕЗУЛЬТАТ ---
    image = models.ImageField("Изображение", upload_to=upload_to, blank=True, null=True)
    generation_status = models.CharField(
        "Статус генерации", max_length=20, default="pending", choices=STATUS_CHOICES
    )
    error_message = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Проект промпт"
        verbose_name_plural = "Проекты промптов"
        ordering = ["order"]  # Всегда сортировать по порядку

    @property
    def smart_image_url(self):
        """
        Динамически возвращает путь к картинке в новой структуре папок проекта.
        Если картинка еще не сгенерирована, возвращает None.
        """
        if self.generation_status != "success":
            return None

        # 1. Берём заголовок проекта
        project_title = self.project.title
        # 1. Добавили транслитерацию, чтобы дашборд искал латинскую папку
        safe_title = transliterate(project_title)

        # 2. Очищаем его точно так же, как при создании папки
        clean_title = re.sub(r'[\\/*?:"<>| ]', "_", safe_title)
        clean_title = re.sub(r"_+", "_", clean_title).strip("_")
        folder_name = clean_title[:100]

        # 3. Формируем номер сцены и имя файла
        scene_index = self.order
        filename = f"pic_{scene_index}.png"

        # 4. Возвращаем правильный URL для фронтенда
        return f"{settings.MEDIA_URL}projects/{folder_name}/{filename}"

    def __str__(self):
        return f"Scene {self.order} - Project {self.project.id}"
