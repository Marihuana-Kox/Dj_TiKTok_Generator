import sys
import traceback
from .forms import GenerateIdeasForm
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import VideoProject
# Нам понадобится форма (см. ниже)
from .forms import GenerateIdeasForm, VideoProjectEditForm
from .services import generate_unique_ideas


def dashboard(request):
    # Статистика
    stats = {
        'total': VideoProject.objects.count(),
        'new': VideoProject.objects.filter(status='pending').count(),
        'done': VideoProject.objects.filter(status='completed').count(),
    }
    # Список последних идей
    ideas = VideoProject.objects.all().order_by('-created_at')[:50]

    context = {
        'stats': stats,
        'ideas': ideas,
    }
    return render(request, 'topics/dashboard.html', context)


def generate_idea_view(request):
    if request.method == 'POST':
        form = GenerateIdeasForm(request.POST)
        if form.is_valid():
            topic = form.cleaned_data['topic']
            count = form.cleaned_data['count']

            try:
                created_count = generate_unique_ideas(count=count, topic=topic)
                messages.success(
                    request, f"✅ Успешно сгенерировано {created_count} новых идей!")
                return redirect('topics:dashboard')
            except Exception as e:
                messages.error(request, f"❌ Ошибка: {str(e)}")
    else:
        form = GenerateIdeasForm()

    return render(request, 'topics/generate.html', {'form': form})


def project_edit(request, pk):
    # Получаем проект или 404
    project = get_object_or_404(VideoProject, pk=pk)

    if request.method == 'POST':
        form = VideoProjectEditForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Идеи успешно сохранены!")
            # Перезагружаем страницу, чтобы увидеть изменения
            return redirect('topics:project_edit', pk=pk)
        else:
            messages.error(request, "❌ Ошибка при сохранении. Проверьте поля.")
    else:
        # Если GET запрос, просто создаем форму с текущими данными
        form = VideoProjectEditForm(instance=project)

    context = {
        'form': form,
        'project': project
    }
    return render(request, 'topics/project_edit.html', context)


def generate_idea_view(request):
    if request.method == 'POST':
        form = GenerateIdeasForm(request.POST)
        if form.is_valid():
            provider_name = form.cleaned_data['ai_provider']
            count = form.cleaned_data['count']
            topics_raw = form.cleaned_data.get('topics_input', '')
            focus_topics = [t.strip()
                            for t in topics_raw.split('\n') if t.strip()]
            main_topic = ", ".join(focus_topics) if focus_topics else "История"

            refresh_old = form.cleaned_data.get('refresh_old', False)
            refresh_period = int(form.cleaned_data.get(
                'refresh_period', 30)) if refresh_old else None

            allow_duplicates = form.cleaned_data.get('allow_duplicates', False)
            duplicate_period = int(form.cleaned_data.get(
                'duplicate_period', 30)) if not allow_duplicates else None

            print(
                f"\n🚀 START GENERATION: Provider={provider_name}, Count={count}")

            try:
                # Вызов сервиса
                created_count = generate_unique_ideas(
                    provider_name=provider_name,
                    count=count,
                    topic=main_topic,
                    focus_topics=focus_topics,
                    refresh_old=refresh_old,
                    refresh_days=refresh_period,
                    allow_duplicates=allow_duplicates,
                    no_duplicate_days=duplicate_period
                )

                print(f"✅ SUCCESS: Created {created_count} ideas.")
                messages.success(
                    request, f"✅ {provider_name.upper()} сгенерировал {created_count} идей!")
                return redirect('topics:dashboard')

            except Exception as e:
                # ЛОВИМ ОШИБКУ И ВЫВОДИМ ПОДРОБНОСТИ
                error_msg = str(e)
                full_traceback = traceback.format_exc()

                print(f"\n❌ CRITICAL ERROR DURING GENERATION:")
                print(f"Error Message: {error_msg}")
                print(f"Traceback:\n{full_traceback}")
                print("-" * 50)

                # Показываем ошибку пользователю в интерфейсе
                messages.error(
                    request, f"❌ Ошибка генерации ({provider_name}): {error_msg}")
                # Возвращаем пользователя обратно на форму, чтобы он не потерял введенные данные
                return render(request, 'topics/generate.html', {'form': form})
        else:
            print("⚠️ Form is invalid:", form.errors)
            messages.error(request, "Проверьте правильность заполнения формы.")
    else:
        form = GenerateIdeasForm()

    return render(request, 'topics/generate.html', {'form': form})
