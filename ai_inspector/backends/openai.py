from .base import BaseAIBackend
from openai import OpenAI
import json


class OpenAIBackend(BaseAIBackend):
    def __init__(self, provider):
        super().__init__(provider)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = self.config.get('model', 'gpt-4o')

    def generate_text(self, prompt: str, **kwargs) -> str:
        params = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.config.get('temperature', 0.7),
            **kwargs
        }
        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content

    def generate_image(self, prompt: str, **kwargs) -> bytes:
        # Реализация через DALL-E или возврат заглушки, если используем HF для картинок
        raise NotImplementedError(
            "Image generation via OpenAI not implemented yet.")
