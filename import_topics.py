from generator.models import VideoProject
import os
import django
import json

# Настройка окружения Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktok_web.settings')
django.setup()


def import_topics(json_file_path):
    print(f"📂 Читаем файл: {json_file_path}...")

    if not os.path.exists(json_file_path):
        print("❌ Файл не найден!")
        return

    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]  # Если загружается один объект, а не список

    created_count = 0
    for item in data:
        topic = item.get('topic')

        # Проверяем, нет ли уже такого проекта, чтобы не дублировать
        if VideoProject.objects.filter(topic=topic).exists():
            print(f"⏭️  Пропущено (уже есть): {topic}")
            continue

        # Создаем запись в БД
        project = VideoProject.objects.create(
            topic=topic,
            angle=item.get('angle', ''),
            notes=item.get('notes', ''),
            status=item.get('status', 'pending')
        )
        print(f"✅ Создано: {project.topic}")
        created_count += 1

    print(f"\n🎉 Готово! Импортировано {created_count} новых проектов.")


if __name__ == '__main__':
    import_topics('import_data.json')
