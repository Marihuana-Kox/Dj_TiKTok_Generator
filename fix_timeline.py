import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tiktok_web.settings")
django.setup()

from image.models import ImagePrompt


def fix_structure():
    prompts = ImagePrompt.objects.all()
    print(f"Найдено записей: {prompts.count()}")
    for p in prompts:
        if not p.image or not p.image.name:
            continue

        path = p.image.name
        old_path = path

        # Исправляем склейку проекта с названием папки
        path = path.replace("projectsproekt_", "projects/proekt_")
        path = path.replace("projectsgolod_", "projects/golod_")
        path = path.replace("projectsopasnye_", "projects/opasnye_")
        path = path.replace("projectsvelikaya_", "projects/velikaya_")

        # Исправление путей, где пропало название папки
        if "projects/pic_" in path and len(path.split("/")) == 2:
            path = path.replace("projects/", "projects/Velikaya_lozh_Kolumba/")

        # Возврат точки перед расширением
        if path.endswith("png") and not path.endswith(".png"):
            path = path[:-3] + ".png"

        if old_path != path:
            p.image.name = path
            p.save()
            print(f"Исправлено: {old_path} -> {path}")


if __name__ == "__main__":
    fix_structure()
