# image/services.py
import os
import json
import re
import requests
from django.core.cache import cache
from django.db import transaction
from .models import ImagePrompt, ImageProject
from prompts.models import ImagePromptTemplate
from ai_inspector.models import AIProvider  # Импортируем модель
from django.conf import settings
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from huggingface_hub import InferenceClient
except ImportError:
    InferenceClient = None


def get_ai_client(provider_override=None):
    """
    Универсальная фабрика клиентов.
    Берёт API ключ из модели AIProvider, а не из SystemConfig.
    """
    config = AIProvider.objects.filter(
        is_active=True).order_by('provider_type', 'name')

    # Определяем провайдера
    if provider_override:
        provider_code = provider_override.lower()
    else:
        # Если нет переопределения, берем текущего из SystemConfig
        from config.models import SystemConfig
        config = SystemConfig.get_config()
        provider_code = getattr(config, 'current_provider', 'openai').lower()

    # Получаем провайдера из БД
    try:
        provider_obj = AIProvider.objects.get(
            name=provider_code, is_active=True)
    except AIProvider.DoesNotExist:
        raise ValueError(
            f"Провайдер '{provider_code}' не найден или неактивен в БД!")

    # Получаем расшифрованный API ключ
    api_key = provider_obj.get_api_key()

    if not api_key:
        raise ValueError(
            f"API ключ для провайдера '{provider_code}' не настроен!")

    # === БЕРЁМ МОДЕЛЬ ИЗ provider_obj.config['model_id'] ===
    model_name = provider_obj.config.get('model_id')
    if not model_name:
        raise ValueError(
            f"Модель не указана в настройках провайдера '{provider_code}'!")

    print(f"📌 Провайдер: {provider_code}, Модель: {model_name}")

    # Возвращаем клиента
    if provider_code == 'openai':
        if not OpenAI:
            raise ImportError("Установи: pip install openai")
        client = OpenAI(api_key=api_key)
        return client, model_name, provider_code

    elif provider_code == 'huggingface':
        if not InferenceClient:
            raise ImportError("Установи: pip install huggingface_hub")
        client = InferenceClient(token=api_key)
        return client, model_name, provider_code

    elif provider_code == 'gemini':
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        return model, model_name, provider_code

    else:
        raise ValueError(f"Неподдерживаемый провайдер: {provider_code}")


def call_llm_universal(prompt_text, provider_override=None):
    """Отправляет запрос в AI, используя текущего провайдера."""
    client, model_name, provider = get_ai_client(provider_override)

    print(f"\n>>> ВЫЗОВ AI: Провайдер={provider}, Модель={model_name}")

    if provider == 'openai':
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system",
                    "content": "You are a helpful assistant that outputs valid JSON."},
                {"role": "user", "content": prompt_text}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return response.choices[0].message.content

    elif provider == 'huggingface':
        try:
            output = client.chat_completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=2500,
                temperature=0.7
            )
            return output.choices[0].message.content
        except Exception:
            output = client.text_generation(prompt_text, max_new_tokens=2500)
            return output

    elif provider == 'gemini':
        response = client.generate_content(prompt_text)
        return response.text

    else:
        raise ValueError(f"Логика для провайдера {provider} не реализована")


def parse_ai_response(raw_response):
    """
    Парсит ответ от AI и возвращает список сцен.
    Обрабатывает разные форматы JSON и очищает от markdown.
    """
    print(f"\n{'='*60}")
    print(f"СЫРОЙ ОТВЕТ AI (первые 2000 символов):")
    print(f"{'='*60}")
    print(raw_response)
    print(repr(raw_response[:2000]))  # repr() покажет экранированные символы
    print(f"======================\n")

    try:
        # 1. Очищаем от markdown-блоков (```json ... ```)
        cleaned = raw_response.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()

        # 2. Ищем JSON массив в тексте
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            json_str = match.group()
        else:
            json_str = cleaned

        print(f"=== JSON ДЛЯ ПАРСИНГА ===")
        print(json_str[:500])
        print(f"========================\n")

        # 3. Парсим JSON
        scenes_data = json.loads(json_str)

        # 4. Нормализуем
        if not isinstance(scenes_data, list):
            if isinstance(scenes_data, dict):
                if 'prompts' in scenes_data:
                    scenes_data = [{"scene_description": f"Scene {i+1}", "prompt_text": p}
                                   for i, p in enumerate(scenes_data['prompts'])]
                elif 'scenes' in scenes_data:
                    scenes_data = scenes_data['scenes']
                else:
                    scenes_data = [scenes_data]
            else:
                raise ValueError(f"Неожиданный формат: {type(scenes_data)}")

        # 5. Проверяем каждую сцену на наличие нужных полей
        normalized = []
        for i, scene in enumerate(scenes_data):
            if isinstance(scene, dict):
                normalized.append({
                    'scene_description': scene.get('scene_description', scene.get('description', f'Scene {i+1}')),
                    'prompt_text': scene.get('prompt_text', scene.get('prompt', ''))
                })
            else:
                normalized.append({
                    'scene_description': f'Scene {i+1}',
                    'prompt_text': str(scene)
                })

        print(f"✅ Успешно распарсено {len(normalized)} сцен")
        return normalized

    except json.JSONDecodeError as e:
        print(f"!!! ОШИБКА JSON: {e}")
        print(f"Полный ответ AI: {raw_response}")
        raise Exception(f"AI вернул невалидный JSON: {e}")
    except Exception as e:
        print(f"!!! ОШИБКА ПАРСИНГА: {e}")
        raise Exception(f"Ошибка обработки ответа AI: {e}")


# def generate_storyboard(project, scenes_count=10, provider_override=None, task_id=None):
def generate_storyboard(project, scenes_count, provider_override, task_id, prompt_template=None, source_text=None, **kwargs):
    """
    Генерация раскадровки с реальным обновлением прогресса.
    """
    if not prompt_template:
        raise ValueError("prompt_template не передан")

    def log_step(percent, message):
        if task_id:
            data = cache.get(f"progress_{task_id}", {})
            logs = data.get('logs', [])
            if message and (not logs or logs[-1] != message):
                logs.append(message)
            cache.set(f"progress_{task_id}", {
                'percent': percent,
                'message': message,
                'status': 'running',
                'logs': logs[-15:],
                'task_id': task_id
            }, timeout=3600)

    # --- 1. Подготовка промпта ---
    trans = project.article.translations.filter(
        language__code='ru').first() or project.article.translations.first()
    if not trans or not trans.content:
        raise ValueError("Текст статьи не найден.")

    source_text = trans.content[:4000]
    template_obj = ImagePromptTemplate.objects.filter(
        code_name='storyboard_generator', is_active=True).first()
    if not template_obj:
        raise Exception("Шаблон 'storyboard_generator' не найден.")

    final_prompt = prompt_template.format(
        scenes_count=scenes_count,
        aspect_ratio=project.aspect_ratio,
        language="Russian",
        style_preset=project.style_preset,
        source_text=source_text
    )

    # --- 2. Ожидание AI (самый долгий этап) ---
    log_step(15, "🤖 AI формирует сюжетные линии (обычно 10-20 сек)...")
    raw_response = call_llm_universal(final_prompt, provider_override)

    # --- 3. Парсинг ---
    log_step(50, "📥 Обработка ответа и создание сцен...")
    scenes_data = parse_ai_response(raw_response)
    total_scenes = len(scenes_data)

    # --- 4. Сохранение в БД (РЕАЛЬНЫЙ ПРОГРЕСС ТУТ) ---
    with transaction.atomic():
        project.prompts.all().delete()
        for i, item in enumerate(scenes_data):
            num = i + 1
            desc = item.get('scene_description', item.get(
                'description', f'Scene {num}'))
            txt = item.get('prompt_text', item.get('prompt', ''))

            ImagePrompt.objects.create(
                project=project,
                order=num,
                scene_description=desc,
                prompt_text=txt,
                generation_status='pending'
            )

            # Динамический расчет: начинаем с 55% и доходим до 98%
            progress_percent = 55 + int((num / total_scenes) * 40)
            log_step(progress_percent,
                     f"✅ Сцена {num}/{total_scenes} сохранена: {desc[:40]}...")

        project.prompts_generated = True
        project.status = 'prompts_ready'
        project.save()

    return total_scenes


def generate_image_from_prompt(prompt, provider_name: str, aspect_ratio: str = None, style_preset: str = 'current', task_id=None, step_info=""):
    """
    Генерирует изображение для одного промпта.
    """
    def log_image_step(message):
        if task_id:
            data = cache.get(f"progress_{task_id}", {})
            logs = data.get('logs', [])
            logs.append(f"{step_info} {message}")
            data['logs'] = logs[-15:]
            cache.set(f"progress_{task_id}", data, timeout=3600)
    # Обновляем статус
    prompt.generation_status = 'generating'
    prompt.save()
    log_image_step("🔄 Запуск нейросети...")

    try:
        # Получаем провайдера
        provider = AIProvider.objects.get(name=provider_name, is_active=True)
        api_key = provider.get_api_key()
        config = provider.config
        model_id = config.get('model_id')

        # Получаем клиент
        client, model, provider_type = _get_image_client(
            provider, api_key, config)

        # Размер: из параметра или из проекта
        size = _aspect_ratio_to_size(
            aspect_ratio or prompt.project.aspect_ratio)

        # Стиль: модифицируем промпт
        final_prompt = _apply_style_preset(
            prompt.prompt_text, style_preset, prompt.project)

        # Генерация
        if provider_type == 'huggingface':
            # HuggingFace возвращает PIL Image
            image = client.text_to_image(
                final_prompt,
                width=size['width'],
                height=size['height'],
                num_inference_steps=config.get(
                    'default_params', {}).get('num_inference_steps', 28)
            )

            # Сохранение PIL Image
            filename = f"prompt_{prompt.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            rel_path = os.path.join(
                'image_projects', str(prompt.project.id), filename)
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            image.save(abs_path)  # ✅ .save() для PIL

        elif provider_type == 'replicate':
            # Replicate возвращает URL
            output = client.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": final_prompt,
                    "aspect_ratio": aspect_ratio or "9:16",
                    "num_inference_steps": config.get('default_params', {}).get('num_inference_steps', 4),
                    "guidance_scale": config.get('default_params', {}).get('guidance_scale', 3.5)
                }
            )

            response = requests.get(output[0])

            # Сохранение байтов
            filename = f"prompt_{prompt.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            rel_path = os.path.join(
                'image_projects', str(prompt.project.id), filename)
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'wb') as f:
                f.write(response.content)  # ✅ write() для байтов

        else:
            raise ValueError(f"Неподдерживаемый провайдер: {provider_name}")

        # Обновляем промпт (ОБЩЕЕ для всех провайдеров)
        prompt.image = rel_path
        prompt.generation_status = 'success'
        prompt.save()

        print(f"✅ Изображение сохранено: {rel_path}")
        return rel_path

    except Exception as e:
        prompt.generation_status = 'failed'
        prompt.error_message = str(e)
        prompt.save()
        print(f"❌ Ошибка генерации: {e}")
        raise


def _apply_style_preset(prompt_text: str, style_preset: str, project) -> str:
    """Применяет стиль к промпту"""
    if style_preset == 'current':
        style_keywords = getattr(project, 'get_style_full', lambda: '')()
        return f"{prompt_text}, {style_keywords}" if style_keywords else prompt_text
    elif style_preset == 'cinematic':
        return f"{prompt_text}, cinematic lighting, dramatic shadows, high contrast, 8k, photorealistic"
    elif style_preset == 'anime':
        return f"{prompt_text}, anime style, studio ghibli, vibrant colors, detailed"
    elif style_preset == 'realistic':
        return f"{prompt_text}, photorealistic, 8k, highly detailed, natural lighting"
    elif style_preset == 'artistic':
        return f"{prompt_text}, artistic, painterly style, oil painting, dramatic"
    return prompt_text  # 'custom' или неизвестный — как есть


def _aspect_ratio_to_size(aspect_ratio: str) -> dict:
    """Конвертирует aspect_ratio в пиксели"""
    sizes = {
        '9:16': {'width': 1080, 'height': 1920},
        '16:9': {'width': 1920, 'height': 1080},
        '1:1': {'width': 1024, 'height': 1024},
        '21:9': {'width': 2560, 'height': 1080},
    }
    return sizes.get(aspect_ratio, sizes['9:16'])


def _get_image_client(provider, api_key: str, config: dict):
    """Возвращает клиент для генерации изображений"""
    model_id = config.get('model_id')

    if provider.name in ['huggingface', 'huggingface_image']:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=api_key, model=model_id)
        return client, model_id, 'huggingface'
    elif provider.name == 'replicate':
        import replicate
        client = replicate.Client(api_token=api_key)
        return client, model_id, 'replicate'

    raise ValueError(f"Неизвестный image-провайдер: {provider.name}")
