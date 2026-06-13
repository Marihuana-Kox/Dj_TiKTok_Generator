import uuid
import threading
import json
import time
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import render, redirect

# Импорты
from .forms import GeneratePlanForm
from .models import StoryPlan
from topics.models import ResearchProject
from shorts.progressbar import ProgressManager, sse_progress_view  # Из твоего knowledge base
from django.shortcuts import render

CACHE_TIMEOUT = 3600


# Create your views here.
def dashboard(request):
    return render(request, "planner/dashboard.html")


def generate(request):
    """Отображение формы и запуск генерации сюжетного плана с прогресс-баром."""

    if request.method == "POST":
        form = GeneratePlanForm(request.POST)

        if form.is_valid():
            research_project = form.cleaned_data["research_project"]
            provider_name = form.cleaned_data["ai_provider"]
            target_virality = form.cleaned_data.get("target_virality", 8)
            max_facts = form.cleaned_data.get("max_facts", 5)
            target_duration = form.cleaned_data.get("target_duration", 60)

            # 1. Создаем черновик StoryPlan, чтобы сразу получить ID и связать с Research
            plan = StoryPlan.objects.create(
                research_project=research_project,
                cluster=research_project.cluster,  # Наследуем кластер, если он привязан к исследованию
                title=f"План: {research_project.topic}",
                provider=provider_name,
                status="draft",  # Статус изменится на approved после успеха
            )

            task_id = str(uuid.uuid4())
            redirect_url = f"/planner/plan/{plan.pk}/"  # Убедись, что такой URL есть в urls.py

            # 2. Инициализируем ProgressManager
            pb = ProgressManager(task_id=task_id, redirect_url=redirect_url, timeout=CACHE_TIMEOUT)
            pb.init(
                "🚀 Анализ исследовательских данных...", log_msg=f"Тема: {research_project.topic}"
            )

            # 3. Фоновая задача
            def run_generation():
                try:
                    pb.update(
                        20, "🤖 Формирование промпта...", log_msg="Сбор параметров из research_data"
                    )

                    # 🔥 ЗДЕСЬ БУДЕТ ВЫЗОВ ТВОЕГО services.py
                    # from .services import generate_story_plan
                    # story_data = generate_story_plan(
                    #     research_project=research_project,
                    #     provider_name=provider_name,
                    #     target_virality=target_virality,
                    #     max_facts=max_facts,
                    #     target_duration=target_duration
                    # )

                    # --- ВРЕМЕННАЯ ЭМУЛЯЦИЯ ДЛЯ ПРОВЕРКИ ПРОГРЕСС-БАРА ---

                    time.sleep(2)
                    story_data = {
                        "story_type": "Документальный",
                        "virality_score": target_virality,
                        "narrative_style": "MYSTERY",
                        "hook_fact": {
                            "fact": "Тестовый хук из research_data",
                            "reason": "Проверка",
                        },
                        "central_mystery": research_project.research_data.get(
                            "central_mystery", "Тайна"
                        ),
                        "story_structure": {
                            "setup": "...",
                            "development": ["...", "..."],
                            "reveal": "...",
                            "climax": "...",
                            "ending": "...",
                        },
                        "selected_facts": [
                            {
                                "fact": "Факт 1",
                                "role": "development",
                                "selection_reason": "...",
                                "visual_priority": 8,
                                "scene_concept": "Cinematic shot",
                            }
                        ],
                        "discarded_facts": [],
                    }
                    # -------------------------------------------------------

                    pb.update(60, "✅ Структура сюжета построена", log_msg="Валидация JSON")

                    # Сохраняем реальные данные
                    plan.story_data = story_data
                    plan.virality_score = story_data.get("virality_score", target_virality)
                    plan.narrative_style = story_data.get("narrative_style", "UNKNOWN")
                    plan.status = "approved"
                    plan.save()

                    pb.update(90, "💾 Сохранение в базу...", log_msg="Готово")
                    pb.done(100, "✅ Сюжетный план успешно создан!", log_msg="Перенаправление...")

                except Exception as exc:
                    print(f"❌ Ошибка генерации плана {task_id}: {exc}")
                    plan.status = "rejected"
                    plan.save()
                    pb.fail(str(exc))
                finally:
                    from django.db import connection

                    connection.close()

            # Запуск потока
            threading.Thread(target=run_generation, daemon=True).start()

            # 4. Ответ для фронтенда (AJAX для modal.js)
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.content_type == "application/json"
            ):
                return JsonResponse(
                    {
                        "status": "ok",
                        "task_id": task_id,
                        "stream_url": f"/planner/generate_stream/?task_id={task_id}",  # Должен совпадать с urls.py
                    }
                )

            messages.success(request, "Генерация сюжетного плана запущена в фоне.")
            return redirect("planner:dashboard")  # Или куда ведет твой дашборд

        else:
            if request.content_type == "application/json":
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
            messages.error(request, "Ошибка в форме.")

    else:
        form = GeneratePlanForm()
    # Передаем форму в шаблон. Дополнительно можно передать research_data выбранного проекта через JS,
    # но пока просто рендерим форму.
    return render(request, "planner/generate.html", {"form": form})


def detail(request, pk):
    return render(request, "planner/detail.html")


def generate_stream(request):
    """SSE поток для прогресс-бара (использует готовую функцию из progressbar.py)"""
    task_id = request.GET.get("task_id")
    if not task_id:
        return JsonResponse({"error": "No task_id"}, status=400)

    return sse_progress_view(request, task_id, timeout=CACHE_TIMEOUT)
