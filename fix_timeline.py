import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from ai_inspector.models import AIProvider

provider = AIProvider.objects.filter(name="openai", is_active=True).first()
if provider:
    try:
        key = provider.get_api_key()
        print("✅ Ключ расшифрован:")
        print(key)
        print("\n📋 Скопируй его и вставь в .env:")
        print(f"OPENAI_API_KEY={key}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Возможно, проблема в utils.encrypt_key/decrypt_key")
else:
    print("❌ Активный провайдер 'openai' не найден")
