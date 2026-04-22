from django import forms

from topics.models import VideoProject
from ai_inspector.models import AIProvider  # Импортируем модель провайдера


class GenerateIdeasForm(forms.Form):
    # Поле заполняется динамически из активных провайдеров БД
    ai_provider = forms.ChoiceField(
        label="AI Сервис для генерации",
        choices=[],
        required=True,
        widget=forms.Select(attrs={
                            'class': 'form-control', 'style': 'font-weight: 600; color: var(--accent-blue);'})
    )

    count = forms.IntegerField(
        label="Количество идей", min_value=1, max_value=20, initial=5,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    topics_input = forms.CharField(
        label="Фокусные темы (через запятую)",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Например:\nСветские новости про Сергея Зверева\nДональд Трамп и жена Макрона\nИсторические фальсификации про Египет'
        }),
        help_text="Оставьте пустым для случайных тем из истории."
    )

    refresh_old = forms.BooleanField(
        label="Обновлять старые идеи", required=False, initial=False)
    REFRESH_CHOICES = [
        ('30', 'Старше 1 месяца'),
        ('20', 'Старше 20 дней'),
        ('60', 'Старше 2 месяцев'),
        ('90', 'Старше 3 месяцев'),
    ]
    refresh_period = forms.ChoiceField(
        label="Период для обновления",
        choices=REFRESH_CHOICES,
        required=False,
        initial='30',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    allow_duplicates = forms.BooleanField(
        label="Разрешить повторение тем",
        required=False,
        initial=False,
        help_text="Если выключено, система будет избегать похожих тем."
    )
    DUPLICATE_CHOICES = [
        ('20', 'Не повторять раньше 20 дней'),
        ('30', 'Не повторять раньше 30 дней'),
        ('40', 'Не повторять раньше 40 дней'),
        ('60', 'Не повторять раньше 2 месяцев'),
    ]
    duplicate_period = forms.ChoiceField(
        label="Период запрета повторов",
        choices=DUPLICATE_CHOICES,
        required=False,
        initial='30',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Получаем все активные провайдеры из БД
        active_providers = AIProvider.objects.filter(
            is_active=True).order_by('display_name', 'name')

        choices = [('', '--- Выберите AI сервис ---')]
        for provider in active_providers:
            display_name = provider.display_name or provider.name.capitalize()
            if provider.config and isinstance(provider.config, dict):
                model = provider.config.get('text_model', '')
                if model:
                    short_model = model.split('/')[-1].split('-')[0]
                    display_name += f" ({short_model})"

            choices.append((provider.name, display_name))

        if len(choices) == 1:
            choices = [('', '--- Нет активных сервисов ---')]
            self.fields['ai_provider'].widget.attrs['disabled'] = True

        self.fields['ai_provider'].choices = choices
        if choices and choices[0][0]:
            self.fields['ai_provider'].initial = choices[0][0]


class VideoProjectEditForm(forms.ModelForm):
    class Meta:
        model = VideoProject
        fields = ['topic', 'angle', 'notes', 'status']
        widgets = {
            'topic': forms.TextInput(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;',
                'placeholder': 'Тема...'
            }),
            'angle': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'style': 'width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;',
                'placeholder': 'Идея...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,  # Уменьшили количество строк
                'style': 'width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem; font-family: monospace;',
                'placeholder': 'Сценарий...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; font-size: 0.95rem;'
            }),
        }
        labels = {
            'topic': 'Тема',
            'angle': 'Идея (Hook)',
            'notes': 'Сценарий',
            'status': 'Статус'
        }
