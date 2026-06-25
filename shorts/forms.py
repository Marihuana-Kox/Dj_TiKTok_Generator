from django import forms
from ai_inspector.models import AIProvider
from planner.models import StoryPlan  # Импортируем модель плана


class ShortGenerationForm(forms.Form):
    ai_provider = forms.ChoiceField(
        label="AI Провайдер",
        choices=[],
        required=True,
        widget=forms.Select(attrs={"class": "form-control", "style": "font-weight: 600;"}),
    )

    story_plan = forms.ModelChoiceField(
        label="Сюжетный план (Основа)",
        queryset=StoryPlan.objects.filter(status__in=["approved", "script_generated"]).order_by(
            "-virality_score", "-created_at"
        ),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Сценарий будет написан строго на основе структуры и фактов этого плана.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        providers = AIProvider.objects.filter(is_active=True, provider_type="llm").order_by(
            "display_name"
        )
        self.fields["ai_provider"].choices = [("", "--- Выберите AI ---")] + [
            (p.name, p.display_name) for p in providers
        ]
        if len(self.fields["ai_provider"].choices) > 1:
            self.fields["ai_provider"].initial = self.fields["ai_provider"].choices[1][0]
        # 2. Настройка Сюжетных планов
        # Задаем красивую пустую строку по умолчанию вместо стандартных дефисов "---------"
        self.fields["story_plan"].empty_label = "--- Выберите план ---"
        # --- ВОТ КОД ДЛЯ ОБРЕЗКИ СТРОКИ ДО 40 СИМВОЛОВ ---
        # Заменяем стандартное строковое отображение объектов в списке
        self.fields["story_plan"].label_from_instance = lambda obj: (
            obj.title[:37] + "..." if len(obj.title) > 40 else obj.title
        )
        # Автоматически подставляем самый первый (лучший по вирулентности/свежий) план
        first_plan = self.fields["story_plan"].queryset.first()
        if first_plan:
            self.fields["story_plan"].initial = first_plan
