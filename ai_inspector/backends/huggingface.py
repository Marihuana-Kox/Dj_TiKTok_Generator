import json
import time
import io
from .base import BaseAIBackend, register_backend
from huggingface_hub import InferenceClient


@register_backend('huggingface')
class HuggingFaceBackend(BaseAIBackend):
    def __init__(self, api_key: str, config: dict):  # Как в базовом классе
        super().__init__(api_key, config)
        self.model_id = config.get(
            'model_id', 'runwayml/stable-diffusion-v1-5')
        self.client = InferenceClient(token=self.api_key)

        # Дефолтная модель (самая стабильная)
        default_model = "runwayml/stable-diffusion-v1-5"

        if not self.model_id:
            self.model_id = default_model

        # 3. Инициализируем клиент
        self.client = InferenceClient(token=self.api_key)

        # Отладочный вывод, чтобы видеть, что именно используется
        print(f"DEBUG: HF Backend initialized.")
        print(f"DEBUG: Model ID from DB: '{self.model_id}'")
        print(f"DEBUG: Token length: {len(self.api_key)}")

    def generate_text(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError(
            "Text generation via HF not implemented in this version.")

    def generate_image(self, prompt: str, **kwargs) -> bytes:
        print(f"🎨 Generating image via HF: {self.model_id}...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Параметры из конфига (steps, guidance_scale и т.д.)
                params = {}
                if isinstance(self.provider.config, dict):
                    params = self.provider.config.get('parameters', {})

                # Добавляем параметры из kwargs (если передали явно)
                params.update(kwargs)

                # Вызов клиента
                image = self.client.text_to_image(
                    prompt=prompt,
                    model=self.model_id,
                    **params
                )

                # Конвертация в байты
                if hasattr(image, 'tobytes'):
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    img_bytes = img_byte_arr.getvalue()

                    if len(img_bytes) > 1000:
                        print(
                            f"✅ Image generated successfully ({len(img_bytes)} bytes).")
                        return img_bytes
                    else:
                        raise RuntimeError(
                            "Generated image data is too small.")

                elif isinstance(image, bytes):
                    return image

                else:
                    raise RuntimeError(
                        f"Unknown image format returned: {type(image)}")

            except Exception as e:
                err_msg = str(e)

                # Обработка загрузки модели
                if "Model is currently loading" in err_msg or "503" in err_msg:
                    wait_time = 20
                    print(
                        f"⏳ Model is loading ({attempt+1}/{max_retries}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Четкие ошибки
                if "401" in err_msg or "Invalid token" in err_msg:
                    raise PermissionError("Invalid HF Token.")
                if "403" in err_msg or "access denied" in err_msg.lower():
                    raise PermissionError(
                        "Access Denied. Accept license on HF website.")
                if "404" in err_msg or "not found" in err_msg.lower():
                    # Выводим имя модели, которое вызвало ошибку
                    raise ValueError(
                        f"Model not found: '{self.model_id}'. Check spelling or access rights.")

                raise RuntimeError(f"HF Error: {err_msg}")

        raise RuntimeError("Failed after retries (model stuck in loading).")

    def generate_text(self, prompt: str, **kwargs) -> str:
        """
        Генерация текста через HF Chat Completion.
        Исправлен конфликт параметров temperature/max_tokens.
        """
        text_model = self.config.get(
            'text_model', 'mistralai/Mistral-7B-Instruct-v0.3')

        print(f"📝 Generating text via HF Chat: {text_model}...")

        try:
            # 1. Берем параметры из конфига БД
            # .copy() чтобы не менять оригинал
            params = self.config.get('text_parameters', {}).copy()

            # 2. Добавляем/перезаписываем параметры из kwargs (если передали явно в коде)
            params.update(kwargs)

            # 3. Убираем параметры, которые не нужны или могут вызвать конфликт в chat_completion
            # Возвращать полный текст не нужно, нам нужен только ответ ассистента
            params.pop('return_full_text', None)

            # Формируем сообщение
            messages = [
                {"role": "user", "content": prompt}
            ]

            # 4. Вызов клиента.
            # Передаем model, messages и РАСПАКОВЫВАЕМ params.
            # Все настройки (temperature, max_tokens и т.д.) теперь идут только из params.
            response = self.client.chat_completion(
                model=text_model,
                messages=messages,
                **params
            )

            if not response or not response.choices:
                raise RuntimeError("Empty response from HF chat completion.")

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Model returned empty content.")

            return content

        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg:
                raise PermissionError("Invalid HF Token.")
            if "403" in err_msg or "gated" in err_msg.lower():
                raise PermissionError(
                    f"Access Denied for '{text_model}'. Accept license on HF website.")
            if "404" in err_msg:
                raise ValueError(f"Model not found: '{text_model}'.")
            if "multiple values" in err_msg:
                # На случай если конфликт остался
                raise RuntimeError(
                    f"Parameter conflict: {err_msg}. Check your JSON config for duplicates.")

            raise RuntimeError(f"HF Text Error: {err_msg}")
