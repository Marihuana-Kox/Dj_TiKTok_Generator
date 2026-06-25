from django import forms
from ai_inspector.models import AIProvider
from prompts.models import ArticlePrompt, IdeaPrompt
from topics.models import ResearchProject, VideoProject
from article.models import Language  # Импортируем модель языков


class ArticleGenerationForm(forms.Form):
    # --- Блок 1: Основное ---
    ai_provider = forms.ChoiceField(
        label="AI Сервис", choices=[], widget=forms.Select(attrs={"class": "form-control"})
    )

    article_prompt = forms.ChoiceField(
        label="Промпт статьи", choices=[], widget=forms.Select(attrs={"class": "form-control"})
    )

    # --- Блок 2: Языки (Динамический список) ---
    # Мы не используем MultipleChoiceField здесь, чтобы иметь полный контроль над HTML (checkboxes с disabled)
    # Передадим список языков через конструктор и отрендерим вручную в шаблоне
    languages = forms.MultipleChoiceField(
        label="Языки публикации", choices=[], widget=forms.CheckboxSelectMultiple, required=True
    )

    # --- Блок 3: Идеи ---
    idea_selection = forms.MultipleChoiceField(
        label="Выберите идеи",
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "idea-checkbox"}),
        required=True,
    )

    # --- Блок 4: Настройки Изображений ---
    image_mode = forms.ChoiceField(
        label="Режим генерации картинок",
        choices=[
            ("auto", "🤖 Автоматически (AI разобьет на сцены)"),
            ("manual", "✋ Вручную (Указать кол-во)"),
        ],
        initial="auto",
        required=False,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    manual_scene_count = forms.IntegerField(
        label="Количество сцен (для ручного режима)",
        min_value=1,
        max_value=20,
        initial=5,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "style": "display:inline-block; width: 80px;"}
        ),
    )

    aspect_ratio = forms.ChoiceField(
        label="Размер изображения",
        choices=[
            ("9:16", "9:16 (Stories/Shorts)"),
            ("16:9", "16:9 (YouTube)"),
            ("1:1", "1:1 (Post)"),
        ],
        initial="9:16",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    art_style = forms.CharField(
        label="Стиль изображений (опционально)",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Например: anime style, dark fantasy, realistic, comic book...",
            }
        ),
    )

    generate_video = forms.BooleanField(
        label="🎥 Генерировать промпты для видео (Beta)", required=False, initial=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Провайдеры
        self.fields["ai_provider"].choices = [
            (p.name, p.name.capitalize())
            for p in AIProvider.objects.filter(is_active=True, provider_type="llm")
        ]

        # 2. Промпты и Планы
        self.fields["article_prompt"].choices = [("random", "🎲 Случайный промпт")] + [
            (p.code_name, p.name) for p in ArticlePrompt.objects.filter(is_active=True)
        ]

        # 3. Языки (Хитрая логика для шаблона)
        # Мы передадим все активные языки, но в шаблоне сами решим, какие заблокировать
        all_langs = Language.objects.filter(is_active=True).order_by("order")
        lang_choices = [(lang.code, f"{lang.flag_emoji} {lang.name}") for lang in all_langs]
        self.fields["languages"].choices = lang_choices

        # По умолчанию выбраны EN и RU
        initial_langs = ["en", "ru"]
        # Проверяем, есть ли RU в списке активных, если нет - убираем
        active_codes = [l.code for l in all_langs]
        self.fields["languages"].initial = [code for code in initial_langs if code in active_codes]

        # 4. Идеи
        ideas = VideoProject.objects.filter(status="pending").order_by("-created_at")
        self.fields["idea_selection"].choices = [
            (idea.id, f"[{idea.topic}] {idea.angle}") for idea in ideas
        ]


class VideoScriptForm(forms.Form):
    """Форма для генерации вирусного текста для ролика."""

    ai_provider = forms.ChoiceField(
        label="AI Провайдер",
        choices=[],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    script_prompt = forms.ChoiceField(
        label="Промпт для генерации",
        choices=[],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Выберите промпт для написания вирусного текста",
    )

    languages = forms.MultipleChoiceField(
        label="Языки (опционально)",
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        help_text="Пока не используется, но можно выбрать для будущих версий",
    )

    research_project = forms.ModelChoiceField(
        label="Исследование",
        queryset=ResearchProject.objects.filter(status="pending").order_by("-created_at"),
        required=True,
        widget=forms.Select(attrs={"class": "form-control", "style": "max-height: 200px;"}),
        help_text="Выберите исследование для написания вирусного текста",
        empty_label="--- Выберите исследование ---",
    )

    focus_notes = forms.CharField(
        label="Дополнительные инструкции",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Например: Сделай акцент на загадках, используй больше вопросов, избегай академического тона...",
            }
        ),
        help_text="Оставьте пустым или добавьте свои пожелания к тексту",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Провайдеры
        providers = AIProvider.objects.filter(is_active=True, provider_type="llm").order_by(
            "display_name"
        )
        self.fields["ai_provider"].choices = [("", "--- Выберите AI ---")] + [
            (p.name, p.display_name) for p in providers
        ]
        if len(self.fields["ai_provider"].choices) > 1:
            self.fields["ai_provider"].initial = self.fields["ai_provider"].choices[1][0]

        # 2. Промпты (ищем все активные промпты для вирусных текстов)
        prompts = ArticlePrompt.objects.filter(is_active=True).order_by("name")
        self.fields["script_prompt"].choices = [(p.code_name, p.name) for p in prompts]
        # По умолчанию выбираем viral_script_writer, если есть
        if prompts.filter(code_name="viral_script_writer").exists():
            self.fields["script_prompt"].initial = "viral_script_writer"

        # 3. Языки (опционально, пока не подключаем)
        languages = Language.objects.filter(is_active=True).order_by("order")
        self.fields["languages"].choices = [
            (lang.code, f"{lang.flag_emoji} {lang.name}") for lang in languages
        ]
        # По умолчанию выбираем русский
        self.fields["languages"].initial = ["ru"]

        # 4. Отображение исследований
        self.fields["research_project"].label_from_instance = lambda obj: (
            f"{obj.topic[:50]}..." if len(obj.topic) > 50 else obj.topic
        )


class ArticleCreateForm(forms.Form):
    """Форма для ручного создания статьи."""

    language = forms.ModelChoiceField(
        label="Язык статьи",
        queryset=Language.objects.filter(is_active=True).order_by("order"),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Основной язык статьи. Потом можно добавить переводы.",
    )

    title = forms.CharField(
        label="Заголовок",
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Введите заголовок статьи"}
        ),
    )

    description = forms.CharField(
        label="Описание (SEO)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Краткое описание для превью (до 200 символов)",
            }
        ),
    )

    content = forms.CharField(
        label="Текст статьи",
        required=True,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 15, "placeholder": "Основной текст статьи..."}
        ),
    )

    hashtags = forms.CharField(
        label="Хештеги",
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "#история #тайны #расследование"}
        ),
        help_text="До 5 хештегов через пробел",
    )

    status = forms.ChoiceField(
        label="Статус",
        choices=[
            ("draft", "Черновик"),
            ("review", "На проверке"),
            ("published", "Опубликовано"),
        ],
        initial="draft",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
