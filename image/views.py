from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from generator.models import VideoProject
from .models import ImagePrompt
from .services import generate_scene_prompts


def image_prompt_editor(request, pk):
    project = get_object_or_404(VideoProject, pk=pk)
    prompts = ImagePrompt.objects.filter(project=project)

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. АВТО-ГЕНЕРАЦИЯ ПРОМПТОВ
        if action == 'auto_generate':
            num_scenes = request.POST.get('num_scenes')  # Может быть пустым
            aspect_ratio = request.POST.get('aspect_ratio', '9:16')

            try:
                # Очищаем старые промпты перед новой генерацией? Или добавляем?
                # Лучше спросить пользователя, но пока очистим для теста
                ImagePrompt.objects.filter(project=project).delete()

                new_prompts = generate_scene_prompts(
                    project,
                    num_scenes=int(num_scenes) if num_scenes else None,
                    aspect_ratio=aspect_ratio
                )

                for i, p_text in enumerate(new_prompts):
                    ImagePrompt.objects.create(
                        project=project,
                        prompt_text=p_text,
                        aspect_ratio=aspect_ratio,
                        order=i
                    )
                messages.success(
                    request, f"✅ Сгенерировано {len(new_prompts)} промптов.")

            except Exception as e:
                messages.error(request, f"❌ Ошибка генерации: {e}")

            return redirect('image:image_prompt_editor', pk=pk)

        # 2. СОХРАНЕНИЕ РУЧНЫХ ПРАВОК
        elif action == 'save_manual':
            # Тут сложная логика обновления списка.
            # Для простоты: удаляем все и создаем заново из формы, или обновляем по ID.
            # Сделаем простое обновление по ID для существующих и создание новых.
            # (Это требует более сложной формы с management forms, пока опустим для краткости)
            # Для MVP: просто перенаправляем назад, а редактирование делаем через JS или отдельные формы
            pass

        # 3. УДАЛЕНИЕ ПРОМПТА
        elif action == 'delete_prompt':
            prompt_id = request.POST.get('prompt_id')
            ImagePrompt.objects.filter(id=prompt_id, project=project).delete()
            messages.info(request, "Промпт удален.")
            return redirect('image:image_prompt_editor', pk=pk)

        # 4. ДОБАВЛЕНИЕ НОВОГО ПРОМПТА ВРУЧНУЮ
        elif action == 'add_prompt':
            new_text = request.POST.get('new_prompt_text')
            aspect = request.POST.get('new_aspect_ratio', '9:16')
            if new_text:
                last_order = prompts.last().order + 1 if prompts.exists() else 0
                ImagePrompt.objects.create(
                    project=project,
                    prompt_text=new_text,
                    aspect_ratio=aspect,
                    order=last_order
                )
            return redirect('image:image_prompt_editor', pk=pk)

    context = {
        'project': project,
        'prompts': prompts,
        'aspect_ratios': ImagePrompt.ASPECT_RATIOS,
    }
    return render(request, 'image/image_prompt_editor.html', context)
