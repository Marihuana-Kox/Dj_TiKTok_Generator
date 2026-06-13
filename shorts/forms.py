from django import forms

from ai_inspector.models import AIProvider


class ShortGenerationForm(forms.Form):
    topic = forms.CharField(
        label="Тема ролика",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Например: Пирамиды Гизы, исчезновение Майя, Атлантида",
            }
        ),
    )
    ai_provider = forms.ChoiceField(
        label="AI сервис",
        choices=[],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        providers = AIProvider.objects.filter(is_active=True, provider_type="llm").order_by(
            "display_name", "name"
        )
        choices = [("", "--- Выберите AI сервис ---")]
        for provider in providers:
            label = provider.display_name or provider.name
            config = provider.config or {}
            model = config.get("model_id") or config.get("model") or config.get("text_model")
            if model:
                label = f"{label} ({model})"
            choices.append((provider.name, label))

        self.fields["ai_provider"].choices = choices
        if len(choices) == 2:
            self.fields["ai_provider"].initial = choices[1][0]
