from ai_inspector.services import generate_text
import os
import django

# Настройка окружения Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktok_web.settings')
django.setup()


prompt = "Write a short funny fact about penguins for TikTok."
print(f"🚀 Отправляем запрос: '{prompt}'")

try:
    text = generate_text('huggingface', prompt)
    print("\n✅ УСПЕХ! Ответ от модели:")
    print("-" * 40)
    print(text)
    print("-" * 40)
except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")
    print("💡 Совет: Проверь лицензию модели на Hugging Face.")
