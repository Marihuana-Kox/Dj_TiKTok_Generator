from .base import BaseAIBackend
from google.genai import Client


class GeminiBackend(BaseAIBackend):
    def __init__(self, provider):
        super().__init__(provider)
        # Инициализируем единый клиент нового SDK
        self.client = Client(api_key=self.api_key)

        # Модели из конфига
        self.text_model = self.config.get('model', 'gemini-2.0-flash')
        self.image_model = self.config.get(
            'image_model', 'imagen-3.0-generate-001')

    def generate_text(self, prompt: str, **kwargs) -> str:
        """Генерация текста через Gemini."""
        try:
            response = self.client.models.generate_content(
                model=self.text_model,
                contents=prompt,
                config={
                    'temperature': self.config.get('temperature', 0.7),
                    'max_output_tokens': self.config.get('max_tokens', 2048),
                }
            )
            if not response.text:
                raise RuntimeError("Empty text response from Gemini.")
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini Text Error: {str(e)}")

    def generate_image(self, prompt: str, **kwargs) -> bytes:
        """
        Генерация изображений через Imagen 3.
        Важно: Никаких лишних параметров в config, только prompt.
        """
        try:
            # Вызов модели Imagen.
            # В новом SDK количество картинок по умолчанию = 1.
            # Параметр number_of_images НЕ передается, чтобы избежать ошибки Pydantic.
            response = self.client.models.generate_content(
                model=self.image_model,
                contents=prompt
            )

            # Проверка наличия кандидатов
            if not response.candidates:
                raise RuntimeError("No candidates returned by Imagen model.")

            # Извлечение частей контента
            parts = response.candidates[0].content.parts
            if not parts:
                raise RuntimeError("No content parts in response.")

            # Поиск блока с изображением (inline_data)
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data:
                    data = getattr(inline_data, "data", None)
                    if data:
                        return data

            raise RuntimeError(
                "Response does not contain inline image data. Check if Imagen 3 is enabled for your project.")

        except Exception as e:
            err_msg = str(e)
            # Более понятные сообщения об ошибках
            if "quota" in err_msg.lower() or "key" in err_msg.lower():
                raise PermissionError(
                    "Invalid API Key or Quota Exceeded for Imagen.")
            if "location" in err_msg.lower() or "unavailable" in err_msg.lower() or "not found" in err_msg.lower():
                raise PermissionError(
                    "Imagen model unavailable in your region or access denied. Check HF or Google Cloud Console.")
            raise RuntimeError(f"Gemini Image Error: {err_msg}")
