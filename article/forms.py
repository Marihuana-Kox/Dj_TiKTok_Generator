from django import forms
from ai_inspector.models import AIProvider
from prompts.models import ArticlePrompt
from topics.models import VideoProject
from article.models import Language  # Импортируем модель языков


class ArticleGenerationForm(forms.Form):
    # --- Блок 1: Основное ---
    ai_provider = forms.ChoiceField(label="AI Сервис", choices=[
    ], widget=forms.Select(attrs={'class': 'form-control'}))

    article_prompt = forms.ChoiceField(label="Промпт статьи", choices=[
    ], widget=forms.Select(attrs={'class': 'form-control'}))

    # --- Блок 2: Языки (Динамический список) ---
    # Мы не используем MultipleChoiceField здесь, чтобы иметь полный контроль над HTML (checkboxes с disabled)
    # Передадим список языков через конструктор и отрендерим вручную в шаблоне
    languages = forms.MultipleChoiceField(
        label="Языки публикации",
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    # --- Блок 3: Идеи ---
    idea_selection = forms.MultipleChoiceField(
        label="Выберите идеи",
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'idea-checkbox'}),
        required=True
    )

    # --- Блок 4: Настройки Изображений ---
    image_mode = forms.ChoiceField(
        label="Режим генерации картинок",
        choices=[('auto', '🤖 Автоматически (AI разобьет на сцены)'),
                 ('manual', '✋ Вручную (Указать кол-во)')],
        initial='auto',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

    manual_scene_count = forms.IntegerField(
        label="Количество сцен (для ручного режима)",
        min_value=1,
        max_value=20,
        initial=5,
        required=False,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'style': 'display:inline-block; width: 80px;'})
    )

    aspect_ratio = forms.ChoiceField(
        label="Размер изображения",
        choices=[('9:16', '9:16 (Stories/Shorts)'),
                 ('16:9', '16:9 (YouTube)'), ('1:1', '1:1 (Post)')],
        initial='9:16',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    art_style = forms.CharField(
        label="Стиль изображений (опционально)",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: anime style, dark fantasy, realistic, comic book...'
        })
    )

    generate_video = forms.BooleanField(
        label="🎥 Генерировать промпты для видео (Beta)",
        required=False,
        initial=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Провайдеры
        self.fields['ai_provider'].choices = [
            (p.name, p.name.capitalize()) for p in AIProvider.objects.filter(is_active=True)]

        # 2. Промпты и Планы
        self.fields['article_prompt'].choices = [('random', '🎲 Случайный промпт')] + [(
            p.code_name, p.name) for p in ArticlePrompt.objects.filter(is_active=True)]

        # 3. Языки (Хитрая логика для шаблона)
        # Мы передадим все активные языки, но в шаблоне сами решим, какие заблокировать
        all_langs = Language.objects.filter(is_active=True).order_by('order')
        lang_choices = [
            (lang.code, f"{lang.flag_emoji} {lang.name}") for lang in all_langs]
        self.fields['languages'].choices = lang_choices

        # По умолчанию выбраны EN и RU
        initial_langs = ['en', 'ru']
        # Проверяем, есть ли RU в списке активных, если нет - убираем
        active_codes = [l.code for l in all_langs]
        self.fields['languages'].initial = [
            code for code in initial_langs if code in active_codes]

        # 4. Идеи
        ideas = VideoProject.objects.filter(
            status='pending').order_by('-created_at')
        self.fields['idea_selection'].choices = [
            (idea.id, f"[{idea.topic}] {idea.angle}") for idea in ideas]
