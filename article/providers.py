import os
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ArticleData:
    title: str
    script_en: str
    translations: Dict[str, str]
    image_prompts: List[str]
    hashtags: str
    structure_plan: dict = None


class BaseProvider(ABC):
    @abstractmethod
    def generate(self, topic: str, angle: str, notes: str, languages: List[str], system_instruction: str = None) -> ArticleData:
        pass

    def _get_lang_name(self, code: str) -> str:
        mapping = {
            'ru': 'Russian', 'de': 'German', 'es': 'Spanish', 'fr': 'French',
            'it': 'Italian', 'pt': 'Portuguese', 'zh': 'Chinese (Mandarin)', 'ja': 'Japanese'
        }
        return mapping.get(code, code)


class OpenAIProvider(BaseProvider):
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        try:
            from openai import OpenAI
            self.key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found")
            self.client = OpenAI(api_key=api_key)
            self.model = model
        except ImportError:
            raise ImportError("pip install openai")

    def _generate_structure_plan(self, topic: str, angle: str, notes: str, template_prompt: str) -> dict:
        """
        Отдельная функция: Генерирует только план статьи на основе шаблона.
        Возвращает словарь (JSON).
        """
        # Подставляем данные пользователя в шаблон
        final_prompt = template_prompt.format(
            topic=topic, angle=angle, notes=notes)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a viral video strategist. Output ONLY valid JSON."},
                {"role": "user", "content": final_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        return json.loads(response.choices[0].message.content)

    def generate(self, topic: str, angle: str, notes: str, languages: List[str],
                 system_instruction: str = None, structure_template: str = None) -> ArticleData:
        # Базовый системный промпт
        base_system = "You are a viral TikTok historian and scriptwriter. You output ONLY valid JSON."
        plan_data = None
        plan_context = ""

        if structure_template:
            # Вызываем нашу новую отдельную функцию
            plan_data = self._generate_structure_plan(
                topic, angle, notes, structure_template)
            # Превращаем план в текст, чтобы скармить его следующему этапу
            plan_context = f"\nSTRICT STRUCTURE TO FOLLOW:\n{json.dumps(plan_data)}\n"
        # Если пользователь задал свой стиль - добавляем его
        if system_instruction:
            system_prompt = f"{base_system}\n\nSTYLE INSTRUCTION: {system_instruction}"
        else:
            system_prompt = base_system

        user_prompt = f"""
        Topic: {topic}
        Angle/Paradox: {angle}
        Key Facts/Notes: {notes}
        {plan_context}

        Task:
        1. Write a dramatic 60s script in ENGLISH strictly following the structure above.
        2. Create 4 short image prompts.
        3. Create a clickbait Title.
        4. Create 5 Hashtags.

        JSON Format:
        {{
            "script_en": "...",
            "image_prompts": ["...", "...", "...", "..."],
            "title": "...",
            "hashtags": "..."
        }}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        data = json.loads(response.choices[0].message.content)

        script_en = data.get('script_en', '')
        prompts = data.get('image_prompts', [])
        title = data.get('title', 'Untitled')
        hashtags = data.get('hashtags', '')

        translations = {}
        for lang_code in languages:
            translations[lang_code] = self._translate_text(
                script_en, lang_code)

        return ArticleData(
            title=title,
            script_en=script_en,
            translations=translations,
            image_prompts=prompts,
            hashtags=hashtags,
            structure_plan=plan_data
        )

    def _translate_text(self, text: str, lang_code: str) -> str:
        lang_name = self._get_lang_name(lang_code)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": f"Translate to {lang_name}. Dramatic tone. No extra text."},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()


class GeminiProvider(BaseProvider):
    def __init__(self, model: str = "gemini-1.5-flash", api_key: str = None):
        try:
            import google.generativeai as genai
            key = api_key or os.getenv("GEMINI_API_KEY")
            if not key:
                raise ValueError("API Key not provided")
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError("pip install google-generativeai")

    def _generate_structure_plan(self, topic: str, angle: str, notes: str, template_prompt: str) -> dict:
        """
        Отдельная функция: Генерирует только план статьи на основе шаблона.
        Возвращает словарь (JSON).
        """
        # Подставляем данные пользователя в шаблон
        final_prompt = template_prompt.format(
            topic=topic, angle=angle, notes=notes)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a viral video strategist. Output ONLY valid JSON."},
                {"role": "user", "content": final_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        return json.loads(response.choices[0].message.content)

    def generate(self, topic: str, angle: str, notes: str, languages: List[str],
                 system_instruction: str = None, structure_template: str = None) -> ArticleData:
        plan_data = None
        plan_context = ""

        if structure_template:
            # Вызываем нашу новую отдельную функцию
            plan_data = self._generate_structure_plan(
                topic, angle, notes, structure_template)
            # Превращаем план в текст, чтобы скармить его следующему этапу
            plan_context = f"\nSTRICT STRUCTURE TO FOLLOW:\n{json.dumps(plan_data)}\n"
        style_prefix = ""

        if system_instruction:
            style_prefix = f"**IMPORTANT STYLE INSTRUCTION**: {system_instruction}\n\n"

        prompt = f"""
        {style_prefix}You are a viral TikTok historian.
        Topic: {topic}
        Angle: {angle}
        Facts: {notes}
        {plan_context} 

        Task:
        1. Write a dramatic 60s script in ENGLISH strictly following the structure above.
        2. Create 4 short image prompts.
        3. Create a clickbait Title.
        4. Create 5 Hashtags.

        JSON Format:
        {{
            "script_en": "...",
            "image_prompts": ["...", "...", "...", "..."],
            "title": "...",
            "hashtags": "..."
        }}
        """

        response = self.model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if text.startswith('{') and text.endswith('}'):
                data = json.loads(text)
            else:
                raise ValueError("Gemini returned invalid JSON.")

        script_en = data.get('script_en', '')
        prompts = data.get('image_prompts', [])
        title = data.get('title', 'Untitled')
        hashtags = data.get('hashtags', '')

        translations = {}
        for lang_code in languages:
            translations[lang_code] = self._translate_text(
                script_en, lang_code)

        return ArticleData(
            title=title,
            script_en=script_en,
            translations=translations,
            image_prompts=prompts,
            hashtags=hashtags,
            structure_plan=plan_data
        )

    def _translate_text(self, text: str, lang_code: str) -> str:
        lang_name = self._get_lang_name(lang_code)
        resp = self.model.generate_content(
            f"Translate to {lang_name} (dramatic tone): {text}")
        return resp.text.strip()


def get_provider(name: str) -> BaseProvider:
    providers = {'openai': OpenAIProvider, 'gemini': GeminiProvider}
    if name not in providers:
        raise ValueError(f"Unknown provider: {name}")
    return providers[name]()
