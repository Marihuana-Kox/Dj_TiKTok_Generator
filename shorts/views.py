import uuid
import threading
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .forms import ShortGenerationForm
from .models import ShortProject, ShortScene
from .services import generate_short_script
from .progressbar import ProgressManager, sse_progress_view

CACHE_TIMEOUT = 3600


def dashboard(request):
    projects_qs = ShortProject.objects.prefetch_related("scenes").order_by("-created_at")
    paginator = Paginator(projects_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    stats = {
        "total": ShortProject.objects.count(),
        "ready": ShortProject.objects.filter(status=ShortProject.STATUS_SCRIPT_READY).count(),
        "failed": ShortProject.objects.filter(status=ShortProject.STATUS_FAILED).count(),
    }
    return render(request, "shorts/dashboard.html", {"page_obj": page_obj, "stats": stats})


def generate(request):
    if request.method == "POST":
        form = ShortGenerationForm(request.POST)
        if form.is_valid():
            topic = form.cleaned_data["topic"]
            provider = form.cleaned_data["ai_provider"]

            # 1. Создаём проект и получаем ID для редиректа
            project = ShortProject.objects.create(
                topic=topic,
                provider=provider,
                status=ShortProject.STATUS_PROCESSING,
            )
            task_id = str(uuid.uuid4())
            redirect_url = f"/shorts/{project.pk}/"

            # 2. Инициализируем менеджер прогресса
            pb = ProgressManager(task_id, redirect_url=redirect_url, timeout=CACHE_TIMEOUT)
            pb.init("🚀 Запуск генерации сценария...")

            # 3. Фоновая задача
            def run_generation():
                try:
                    pb.update(15, "🤖 Отправка запроса к AI...", "Промпт сформирован")
                    script_data = generate_short_script(topic=topic, provider_name=provider)

                    pb.update(50, "✅ Сценарий получен. Валидация...", "JSON проверен")

                    project.style = script_data["style"]
                    project.hook = script_data["hook"]
                    project.voiceover = script_data["voiceover"]
                    project.raw_response = script_data
                    project.save()

                    pb.update(80, "🎬 Создание сцен...", "Bulk insert")
                    scenes = [
                        ShortScene(
                            project=project,
                            order=index,
                            text=scene["text"],
                            image_prompt=scene["image_prompt"],
                            duration=scene["duration"],
                        )
                        for index, scene in enumerate(script_data["scenes"], start=1)
                    ]
                    ShortScene.objects.bulk_create(scenes)

                    pb.update(95, "💾 Финализация...", "Готово")
                    project.status = ShortProject.STATUS_SCRIPT_READY
                    project.error_message = ""
                    project.save()

                    pb.done()  # Статус "done" + redirect_url автоматически попадут в SSE

                except Exception as exc:
                    print(f"❌ Ошибка генерации {task_id}: {exc}")
                    project.status = ShortProject.STATUS_FAILED
                    project.error_message = str(exc)
                    project.save()
                    pb.fail(str(exc))
                finally:
                    from django.db import connection

                    connection.close()

            threading.Thread(target=run_generation, daemon=True).start()

            # 4. Ответ для AJAX (modal.js подхватит task_id и сам построит URL стрима)
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.content_type == "application/json"
            ):
                return JsonResponse({"status": "ok", "task_id": task_id})

            messages.success(request, "Генерация запущена в фоне.")
            return redirect("shorts:dashboard")
        else:
            if request.content_type == "application/json":
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
            messages.error(request, "Ошибка в форме.")
    else:
        form = ShortGenerationForm()

    return render(request, "shorts/generate.html", {"form": form})


def generate_stream(request):
    """SSE-эндпоинт, который отдаёт поток данных в modal.js"""
    task_id = request.GET.get("task_id")
    return sse_progress_view(request, task_id, timeout=CACHE_TIMEOUT)


def detail(request, pk):
    project = get_object_or_404(ShortProject.objects.prefetch_related("scenes"), pk=pk)
    return render(request, "shorts/detail.html", {"project": project})
