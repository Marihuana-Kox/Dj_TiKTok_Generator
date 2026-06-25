import uuid
import threading
import json
import time
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Импорты
from .forms import GeneratePlanForm
from .models import StoryPlan
from .services import generate_story_plan
from topics.models import ResearchProject
from shorts.progressbar import ProgressManager, sse_progress_view  # Из твоего knowledge base
from django.shortcuts import render

CACHE_TIMEOUT = 3600


# Create your views here.
def dashboard(request):
    if request.method == "POST":
        action = request.POST.get("action")
        # Имя 'selected_plans' взято строго из твоего HTML: name="selected_plans"
        selected_ids = request.POST.getlist("selected_plans")

        if selected_ids:
            # Получаем queryset выбранных планов
            plans = StoryPlan.objects.filter(id__in=selected_ids)

            if action == "delete_selected":
                count, _ = plans.delete()
                messages.success(request, f"✅ Удалено {count} сюжетных планов.")

            elif action == "change_status":
                new_status = request.POST.get("new_status")
                # Валидация: разрешаем менять только на известные статусы модели
                valid_statuses = ["draft", "approved", "script_generated", "rejected"]

                if new_status in valid_statuses:
                    plans.update(status=new_status)
                    messages.success(
                        request, f"✅ Статус изменен на «{new_status}» для {plans.count()} планов."
                    )
                else:
                    messages.warning(request, "⚠️ Не выбран корректный новый статус.")
        else:
            messages.warning(request, "⚠️ Вы не выбрали ни одного плана для действия.")

        # После обработки POST всегда делаем редирект (паттерн Post/Redirect/Get)
        return redirect("planner:dashboard")
    # 1. Считаем статистику по статусам StoryPlan
    stats = {
        "total": StoryPlan.objects.count(),
        "ready": StoryPlan.objects.filter(status__in=["approved", "script_generated"]).count(),
        "failed": StoryPlan.objects.filter(status="rejected").count(),
        "draft": StoryPlan.objects.filter(status="draft").count(),
    }

    # 2. Получаем список планов с оптимизацией (select_related подтянет тему исследования за 1 запрос)
    plans_list = StoryPlan.objects.select_related("research_project").order_by("-created_at")

    # 3. Настраиваем пагинацию (20 записей на страницу)
    paginator = Paginator(plans_list, 20)
    page_number = request.GET.get("page")

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # 4. Передаем данные в шаблон
    context = {
        "stats": stats,
        "page_obj": page_obj,
    }
    return render(request, "planner/dashboard.html", context)


def generate(request):
    """Отображение формы и запуск генерации сюжетного плана с прогресс-баром."""

    if request.method == "POST":
        form = GeneratePlanForm(request.POST)

        if form.is_valid():
            research_project = form.cleaned_data["research_project"]
            provider_name = form.cleaned_data["ai_provider"]
            print(f"Signal becommt {research_project} - {provider_name}")
            # 🔥 ПРОВЕРКА: есть ли уже approved план для этого исследования?
            existing_plan = StoryPlan.objects.filter(
                research_project=research_project, status="approved"
            ).first()

            if existing_plan:
                print("Prüfung gemacht")
                messages.warning(
                    request,
                    f"️ Для этого исследования уже есть утверждённый план: {existing_plan.title}. "
                    f"Если хотите создать новый, сначала отклоните существующий.",
                )
                return redirect("planner:dashboard")

            print("Weiter gehen")
            # 2. Создаем черновик StoryPlan, чтобы сразу получить ID и связать с Research
            plan = StoryPlan.objects.create(
                research_project=research_project,
                cluster=research_project.cluster,  # Наследуем кластер, если он есть
                title=f"План: {research_project.topic}",
                provider=provider_name,
                status="draft",
            )

            task_id = str(uuid.uuid4())
            redirect_url = f"/planner/detail/{plan.pk}/"  # Убедись, что такой URL есть в urls.py

            # 2. Инициализируем ProgressManager
            pb = ProgressManager(task_id=task_id, redirect_url=redirect_url, timeout=CACHE_TIMEOUT)
            pb.init(
                "🚀 Анализ исследовательских данных...",
                log_msg=f"Тема: {research_project.topic}",
            )

            # 3. Фоновая задача
            def run_generation():
                try:
                    t = 18
                    if t:
                        print(f"Функция запущена: {t}")
                        # 🔥 ЗДЕСЬ БУДЕТ ВЫЗОВ ТВОЕГО services.py
                        story_data = generate_story_plan(
                            research_project=research_project,
                            provider_name=provider_name,
                        )
                    time.sleep(4)
                    pb.update(
                        t, "🤖 Формирование промпта...", log_msg="Сбор параметров из research_data"
                    )
                    # Добавляем статус ожидания, чтобы SSE не "молчал"
                    time.sleep(5)
                    pb.update(
                        30,
                        "⏳ Ожидание ответа от AI...",
                        log_msg="Генерация может занять до 2 минут",
                    )

                    time.sleep(4)
                    pb.update(60, "✅ Структура сюжета построена", log_msg="Валидация JSON")

                    # Сохраняем реальные данные в модель
                    plan.story_data = story_data
                    plan.virality_score = story_data.get("virality_score", 0)
                    plan.narrative_style = story_data.get("narrative_style", "UNKNOWN")
                    plan.status = "approved"
                    plan.save()
                    time.sleep(4)
                    pb.update(88, "💾 Сохранение в базу...", log_msg="Готово")
                    time.sleep(2)
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
    """Отображение детальной страницы сюжетного плана для просмотра и редактирования."""
    # Подтягиваем план и сразу берем тему из связанного исследования
    plan = get_object_or_404(StoryPlan.objects.select_related("research_project"), pk=pk)

    context = {
        "plan": plan,
    }
    return render(request, "planner/detail.html", context)


def generate_stream(request):
    """SSE поток для прогресс-бара (использует готовую функцию из progressbar.py)"""
    task_id = request.GET.get("task_id")
    if not task_id:
        return JsonResponse({"error": "No task_id"}, status=400)

    return sse_progress_view(request, task_id, timeout=CACHE_TIMEOUT)
