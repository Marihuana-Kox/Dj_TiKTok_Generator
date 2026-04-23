from django import forms
from ai_inspector.models import AIProvider
from prompts.models import ArticlePrompt, StructurePlanPrompt
from topics.models import VideoProject


class ArticleGenerationForm(forms.Form):
    ai_provider = forms.ChoiceField(label="AI Сервис", choices=[
    ], widget=forms.Select(attrs={'class': 'form-control'}))
    article_prompt = forms.ChoiceField(label="Промпт статьи", choices=[
    ], widget=forms.Select(attrs={'class': 'form-control'}))
    structure_plan = forms.ChoiceField(label="План статьи", choices=[
    ], widget=forms.Select(attrs={'class': 'form-control'}))
    idea_selection = forms.MultipleChoiceField(label="Доступные идеи", choices=[
    ], widget=forms.CheckboxSelectMultiple(attrs={'class': 'idea-checkbox'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Провайдеры
        self.fields['ai_provider'].choices = [
            (p.name, p.name.capitalize()) for p in AIProvider.objects.filter(is_active=True)]

        # Промпты (+ рандом)
        prompt_choices = [('random', '🎲 Случайный промпт')]
        prompt_choices.extend([(p.code_name, p.name)
                              for p in ArticlePrompt.objects.filter(is_active=True)])
        self.fields['article_prompt'].choices = prompt_choices

        # Планы (+ рандом)
        plan_choices = [('random', '🎲 Случайный план')]
        plan_choices.extend([(p.code_name, p.name)
                            for p in StructurePlanPrompt.objects.filter(is_active=True)])
        self.fields['structure_plan'].choices = plan_choices

        # Идеи (фильтр по статусу 'new' или 'completed' в зависимости от твоей БД)
        ideas = VideoProject.objects.filter(
            status='new').order_by('-created_at')
        self.fields['idea_selection'].choices = [
            (idea.id, f"[{idea.topic}] {idea.angle}") for idea in ideas]
