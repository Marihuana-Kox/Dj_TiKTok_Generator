from django.contrib import admin
from django import forms
from .models import AIProvider


class AIProviderAdminForm(forms.ModelForm):
    # Временное поле для ввода ключа в админке
    api_key_input = forms.CharField(
        label="API Key",
        widget=forms.PasswordInput(
            attrs={'placeholder': 'Оставьте пустым, чтобы не менять'}),
        required=False,
        help_text="Ключ будет зашифрован при сохранении."
    )

    class Meta:
        model = AIProvider
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Если редактируем существующий объект и ключ есть, показываем маску
        if self.instance.pk and self.instance.api_key:
            self.fields['api_key_input'].widget.attrs[
                'placeholder'] = '******** (ключ установлен)'

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_key = self.cleaned_data.get('api_key_input')

        # Обновляем ключ только если пользователь ввел что-то новое
        if new_key:
            instance.set_api_key(new_key)

        if commit:
            instance.save()
        return instance


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    form = AIProviderAdminForm

    list_display = ['name', 'display_name',
                    'provider_type', 'is_active', 'created_at']
    list_filter = ['provider_type', 'is_active']
    search_fields = ['name', 'display_name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Основное', {
            'fields': ['name', 'display_name', 'provider_type', 'is_active']
        }),
        ('Доступ', {
            'fields': ['api_key_input', 'base_url'],
        }),
        ('Настройки модели', {
            'fields': ['config'],
            'description': 'JSON: {"model": "gpt-4o", "temperature": 0.7}'
        }),
        ('Мета', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    )
