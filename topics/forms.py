from django import forms

from topics.helpers.domains import get_preset_choices
from topics.helpers.search_templates import get_category_choices
from topics.models import ResearchProject, VideoProject
from ai_inspector.models import AIProvider  # Импортируем модель провайдера
from prompts.models import IdeaPrompt


class GenerateIdeasForm(forms.Form):
    # Поле заполняется динамически из активных провайдеров БД
    ai_provider = forms.ChoiceField(
        label="AI Сервис для генерации",
        choices=[],
        required=True,
        widget=forms.Select(
            attrs={"class": "form-control", "style": "font-weight: 600; color: var(--accent-blue);"}
        ),
    )

    count = forms.IntegerField(
        label="Количество идей",
        min_value=1,
        max_value=20,
        initial=5,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    # НОВОЕ ПОЛЕ: Выбор стиля промпта
    idea_style = forms.ChoiceField(
        label="Стиль генерации (Промпт)",
        choices=[],  # Заполним динамически в __init__
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "style": "font-weight: 600; color: var(--accent-purple);",
            }
        ),
    )
    topics_input = forms.CharField(
        label="Фокусные темы (через запятую)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Например:\nСветские новости про Сергея Зверева\nДональд Трамп и жена Макрона\nИсторические фальсификации про Египет",
            }
        ),
        help_text="Оставьте пустым для случайных тем из истории.",
    )

    refresh_old = forms.BooleanField(label="Обновлять старые идеи", required=False, initial=False)
    REFRESH_CHOICES = [
        ("30", "Старше 1 месяца"),
        ("20", "Старше 20 дней"),
        ("60", "Старше 2 месяцев"),
        ("90", "Старше 3 месяцев"),
    ]
    refresh_period = forms.ChoiceField(
        label="Период для обновления",
        choices=REFRESH_CHOICES,
        required=False,
        initial="30",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    allow_duplicates = forms.BooleanField(
        label="Разрешить повторение тем",
        required=False,
        initial=False,
        help_text="Если выключено, система будет избегать похожих тем.",
    )
    DUPLICATE_CHOICES = [
        ("20", "Не повторять раньше 20 дней"),
        ("30", "Не повторять раньше 30 дней"),
        ("40", "Не повторять раньше 40 дней"),
        ("60", "Не повторять раньше 2 месяцев"),
    ]
    duplicate_period = forms.ChoiceField(
        label="Период запрета повторов",
        choices=DUPLICATE_CHOICES,
        required=False,
        initial="30",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Получаем все активные провайдеры из БД
        active_providers = (
            AIProvider.objects.filter(is_active=True)
            .filter(provider_type="llm")
            .order_by("display_name", "name")
        )

        choices = [("", "--- Выберите AI сервис ---")]
        for provider in active_providers:
            display_name = provider.display_name or provider.name.capitalize()
            if provider.config and isinstance(provider.config, dict):
                model = provider.config.get("text_model", "")
                if model:
                    short_model = model.split("/")[-1].split("-")[0]
                    display_name += f" ({short_model})"

            choices.append((provider.name, display_name))

        if len(choices) == 1:
            choices = [("", "--- Нет активных сервисов ---")]
            self.fields["ai_provider"].widget.attrs["disabled"] = True

        self.fields["ai_provider"].choices = choices
        if choices and choices[0][0]:
            self.fields["ai_provider"].initial = choices[0][0]

        # 1. Получаем все активные стили из БД
        # Мы берем уникальные комбинации style и name, чтобы показать пользователю красивые названия
        active_prompts = IdeaPrompt.objects.filter(is_active=True).order_by("name")
        # Формируем список вариантов
        style_choices = [
            ("random", "🎲 Случайный стиль (Random)"),  # Опция рандома
        ]

        # Добавляем стили из базы
        for prompt in active_prompts:
            # Просто добавляем пару: (код, имя)
            style_choices.append((prompt.code_name, prompt.name))

        self.fields["idea_style"].choices = style_choices
        self.fields["idea_style"].initial = "random"  # По умолчанию рандом


class VideoProjectEditForm(forms.ModelForm):
    class Meta:
        model = VideoProject
        fields = ["topic", "angle", "notes", "status"]
        widgets = {
            "topic": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                    "placeholder": "Тема...",
                }
            ),
            "angle": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                    "placeholder": "Идея...",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,  # Уменьшили количество строк
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem; font-family: monospace;",
                    "placeholder": "Сценарий...",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-control",
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                }
            ),
        }
        labels = {"topic": "Тема", "angle": "Идея (Hook)", "notes": "Сценарий", "status": "Статус"}


class GenerateResearchForm(forms.Form):
    # 1. Выбор AI-провайдера (динамически из БД)
    ai_provider = forms.ChoiceField(
        label="AI Сервис для исследования",
        choices=[],
        required=True,
        widget=forms.Select(
            attrs={"class": "form-control", "style": "font-weight: 600; color: var(--accent-blue);"}
        ),
    )

    # 2. Тема исследования
    topic = forms.CharField(
        label="Тема исследования",
        required=True,
        max_length=300,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Например: Дамасская сталь, Загадки пирамид, Римские гавани...",
            }
        ),
    )
    search_category = forms.ChoiceField(
        label="🎯 Тип темы (для умного поиска)",
        choices=[],
        initial="general",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Выберите тип темы для более релевантных поисковых запросов.",
    )
    # 3. Переключатель WEB поиска
    use_web_search = forms.BooleanField(
        label="🔍 Искать факты в интернете (Tavily)",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-control checkbox-fix"}),
        help_text="Сначала найти факты в интернете, потом передать их в AI для анализа.",
    )
    # 4. Стиль промпта (динамически из БД)
    research_style = forms.ChoiceField(
        label="Темы промптов для исследования",
        choices=[],
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "style": "font-weight: 600; color: var(--accent-purple);",
            }
        ),
    )

    # 4.1. Выбор пресета доменов
    domain_preset = forms.ChoiceField(
        label="🎯 Источник поиска (опционально)",
        required=False,
        choices=[("", "— Весь интернет —")] + get_preset_choices(),
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Выберите конкретные сайты для поиска. Оставьте пустым для поиска по всему интернету.",
    )
    # 5. Дополнительная информация для поиска
    focus_notes = forms.CharField(
        label="Дополнительные указания (фокус)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        help_text="Например: 'Сосредоточься только на средневековых источниках' или 'Ищи только документальные подтверждения'.",
    )
    # 6. Количество генераций
    count = forms.IntegerField(
        label="Количество исследований",
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ==========================================
        # 1. Загрузка активных провайдеров (LLM)
        # ==========================================
        active_providers = (
            AIProvider.objects.filter(is_active=True)
            .filter(provider_type="llm")
            .order_by("display_name", "name")
        )

        provider_choices = [("", "--- Выберите AI сервис ---")]
        for provider in active_providers:
            display_name = provider.display_name or provider.name.capitalize()
            if provider.config and isinstance(provider.config, dict):
                model = provider.config.get("text_model", "")
                if model:
                    short_model = model.split("/")[-1].split("-")[0]
                    display_name += f" ({short_model})"
            provider_choices.append((provider.name, display_name))

        if len(provider_choices) == 1:
            provider_choices = [("", "--- Нет активных сервисов ---")]
            self.fields["ai_provider"].widget.attrs["disabled"] = True

        self.fields["ai_provider"].choices = provider_choices
        if provider_choices and provider_choices[0][0]:
            self.fields["ai_provider"].initial = provider_choices[0][0]

        # ==========================================
        # 2. Загрузка стилей промптов из БД
        # ==========================================
        # Используем ScriptPrompt (или замени на IdeaPrompt, если нужно)
        active_prompts = (
            IdeaPrompt.objects.filter(
                is_active=True,
            )
            .filter(code_name="research_agent")
            .order_by("name")
        )
        style_choices = [("random", "🎲 Случайный стиль (Auto)")]

        for prompt in active_prompts:
            # Формат строго: (value_for_db, display_name_for_user)
            # Если у модели есть поле style, добавим его в название для красоты
            if hasattr(prompt, "style") and prompt.style:
                display_name = f"{prompt.name} ({prompt.style})"
            else:
                display_name = prompt.name

            style_choices.append((prompt.code_name, display_name))

        self.fields["research_style"].choices = style_choices
        self.fields["research_style"].initial = "random"
        # Выбор категории для создания вариаций запроса поиска
        self.fields["search_category"].choices = get_category_choices()


class ResearchProjectEditForm(forms.ModelForm):
    class Meta:
        model = ResearchProject
        fields = ["topic", "provider", "status", "research_data", "error_message"]
        widgets = {
            "topic": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                    "placeholder": "Тема исследования...",
                }
            ),
            "provider": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                    "placeholder": "AI провайдер...",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-control",
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                }
            ),
            "research_data": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;",
                    "placeholder": "Исследовательские данные (JSON)...",
                }
            ),
            "error_message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "style": "width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: red; border-radius: 6px; font-size: 0.95rem;",
                    "placeholder": "Сообщение об ошибке (если есть)...",
                    "readonly": True,
                }
            ),
        }
        labels = {
            "topic": "Тема исследования",
            "provider": "AI провайдер",
            "status": "Статус",
            "research_data": "Исследовательские данные (JSON)",
            "error_message": "Ошибка (если есть)",
            "created_at": "Дата создания",
            "updated_at": "Дата обновления",
        }
