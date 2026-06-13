from django import forms
from ai_inspector.models import AIProvider
from topics.models import ResearchProject  # Импортируем модель исследования


class GeneratePlanForm(forms.Form):
    ai_provider = forms.ChoiceField(
        label="AI Провайдер",
        choices=[],
        required=True,
        widget=forms.Select(attrs={"class": "form-control", "style": "font-weight: 600;"}),
    )

    research_project = forms.ModelChoiceField(
        label="Исследование (Тема)",
        queryset=ResearchProject.objects.filter(status="pending").order_by("-created_at"),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Выберите готовое исследование, на основе которого будет построен сюжет.",
    )

    # Связанные настройки (с дефолтными значениями, которые можно переопределить)
    target_virality = forms.IntegerField(
        label="Целевой вирусный потенциал (1-10)",
        min_value=1,
        max_value=10,
        initial=8,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    max_facts = forms.IntegerField(
        label="Макс. количество фактов в плане",
        min_value=3,
        max_value=10,
        initial=5,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    target_duration = forms.ChoiceField(
        label="Предполагаемая длина ролика",
        choices=[(60, "60 секунд"), (90, "90 секунд")],
        initial=60,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Динамическая загрузка провайдеров
        providers = AIProvider.objects.filter(is_active=True, provider_type="llm").order_by(
            "display_name"
        )
        provider_choices = [("", "--- Выберите AI сервис ---")] + [
            (p.name, p.display_name) for p in providers
        ]
        self.fields["ai_provider"].choices = provider_choices
        if len(provider_choices) > 1:
            self.fields["ai_provider"].initial = provider_choices[1][0]

        # Переопределяем отображение объектов в выпадающем списке
        self.fields["research_project"].label_from_instance = lambda obj: (
            obj.topic[:37] + "..." if len(obj.topic) > 60 else obj.topic
        )
        last_project = ResearchProject.objects.order_by("-id").first()
        if last_project:
            # Для дефолтного значения используем initial (объект)
            self.fields["research_project"].initial = last_project
