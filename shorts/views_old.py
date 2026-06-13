from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ShortGenerationForm
from .models import ShortProject, ShortScene
from .services import generate_short_script


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

            project = ShortProject.objects.create(
                topic=topic,
                provider=provider,
                status=ShortProject.STATUS_PROCESSING,
            )

            try:
                script_data = generate_short_script(topic=topic, provider_name=provider)
                project.style = script_data["style"]
                project.hook = script_data["hook"]
                project.voiceover = script_data["voiceover"]
                project.raw_response = script_data
                project.status = ShortProject.STATUS_SCRIPT_READY
                project.error_message = ""
                project.save()

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

                messages.success(request, "Сценарий TikTok создан по новой логике.")
                return redirect("shorts:detail", pk=project.pk)
            except Exception as exc:
                project.status = ShortProject.STATUS_FAILED
                project.error_message = str(exc)
                project.save(update_fields=["status", "error_message", "updated_at"])
                messages.error(request, f"Ошибка генерации: {exc}")
                return redirect("shorts:detail", pk=project.pk)
    else:
        form = ShortGenerationForm()

    return render(request, "shorts/generate.html", {"form": form})


def detail(request, pk):
    project = get_object_or_404(ShortProject.objects.prefetch_related("scenes"), pk=pk)
    return render(request, "shorts/detail.html", {"project": project})
