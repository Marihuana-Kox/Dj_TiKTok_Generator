import uuid
import threading
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .forms import ShortGenerationForm
from .models import ShortProject, ShortScene
from .services import generate_short_script_from_plan
from .progressbar import ProgressManager, sse_progress_view

CACHE_TIMEOUT = 3600


def dashboard(request):
    # ==========================================
    # 1. ОБРАБОТКА МАССОВЫХ ДЕЙСТВИЙ (POST)
    # ==========================================
    if request.method == "POST":
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_projects")  # Имя из HTML формы

        if selected_ids:
            projects = ShortProject.objects.filter(id__in=selected_ids)

            if action == "delete_selected":
                count, _ = projects.delete()
                messages.success(request, f"✅ Удалено {count} сценариев.")

            elif action == "change_status":
                new_status = request.POST.get("new_status")
                # Берем допустимые статусы прямо из модели
                valid_statuses = [choice[0] for choice in ShortProject.STATUS_CHOICES]

                if new_status in valid_statuses:
                    projects.update(status=new_status)
                    messages.success(
                        request,
                        f"✅ Статус изменен на «{new_status}» для {projects.count()} сценариев.",
                    )
                else:
                    messages.warning(request, "⚠️ Не выбран корректный новый статус.")
        else:
            messages.warning(request, "⚠️ Вы не выбрали ни одного сценария для действия.")

        return redirect("shorts:dashboard")

    # ==========================================
    # 2. СБОР ДАННЫХ ДЛЯ ОТОБРАЖЕНИЯ (GET)
    # ==========================================
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
            story_plan = form.cleaned_data["story_plan"]
            provider = form.cleaned_data["ai_provider"]

            # 1. Создаём проект. Темой берем название из плана/исследования
            project = ShortProject.objects.create(
                topic=story_plan.title,  # Или story_plan.research_project.topic
                provider=provider,
                status=ShortProject.STATUS_PROCESSING,
            )

            task_id = str(uuid.uuid4())
            redirect_url = f"/shorts/detail/{project.pk}/"

            # 2. Инициализируем менеджер прогресса
            pb = ProgressManager(task_id, redirect_url=redirect_url, timeout=CACHE_TIMEOUT)
            pb.init(
                "🚀 Запуск генерации сценария...", log_msg=f"На основе плана: {story_plan.title}"
            )

            # 3. Фоновая задача
            def run_generation():
                try:
                    pb.update(
                        15,
                        "🤖 Анализ сюжетного плана...",
                        log_msg="Формирование режиссерского промпта",
                    )

                    # 🔥 ВЫЗОВ СЕРВИСА С ГОТОВЫМ ПЛАНОМ
                    script_data = generate_short_script_from_plan(
                        story_plan=story_plan, provider_name=provider
                    )

                    pb.update(50, "✅ Сценарий получен. Валидация...", log_msg="JSON проверен")

                    project.style = script_data["style"]
                    project.hook = script_data["hook"]
                    project.voiceover = script_data["voiceover"]
                    project.raw_response = script_data
                    project.save()

                    pb.update(80, "🎬 Создание сцен...", log_msg="Bulk insert")
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

                    pb.update(95, "💾 Финализация...", log_msg="Готово")
                    project.status = ShortProject.STATUS_SCRIPT_READY
                    project.error_message = ""
                    project.save()

                    pb.done()

                except Exception as exc:
                    print(f"❌ Ошибка генерации {task_id}: {exc}")
                    project.status = ShortProject.STATUS_FAILED
                    project.error_message = str(exc)
                    project.save()
                    pb.fail(str(exc))

                    pb.update(
                        percent=100,
                        message=f"❌ Ошибка: {str(exc)}",
                        log_msg=f"❌ {str(exc)}",
                        status="done",  # modal.js подумает, что задача завершена, и включит таймер
                        redirect_url="/shorts/dashboard/",  # Возвращаем пользователя обратно на форму!
                    )
                finally:
                    from django.db import connection

                    connection.close()

            threading.Thread(target=run_generation, daemon=True).start()

            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.content_type == "application/json"
            ):
                return JsonResponse(
                    {
                        "status": "ok",
                        "task_id": task_id,
                        "stream_url": f"/shorts/generate_stream/?task_id={task_id}",
                    }
                )

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
