import os
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


def clean_text_for_prompt(text: str) -> str:
    """
    Очищает текст от лишних \r, табуляции и нормализует переносы строк.
    Заменяет \r\n и \r на \n, убирает лишние пустые строки по краям.
    """
    if not text:
        return ""
    # Заменяем все виды переносов на стандартный \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Убираем лишние пробелы в начале и конце каждой строки (опционально, но полезно)
    lines = [line.strip() for line in text.split('\n')]
    # Собираем обратно, убирая полностью пустые строки в начале и конце
    cleaned = '\n'.join(lines)
    return cleaned.strip()


def clean_json_response(raw_text: str) -> str:
    """
    Вырезает чистый JSON из ответа AI, удаляя маркдаун, лишний мусор и \r.
    """
    if not raw_text:
        return "{}"

    # 1. Убираем маркдаун блоки ```json ... ```
    text = raw_text.replace('```json', '').replace('```', '').strip()

    # 2. Нормализуем переносы строк внутри строки
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 3. Частая проблема: AI ставит перенос строки ПЕРЕД первой скобкой {
    # Ищем первую '{' и последнюю '}' и вырезаем только содержимое между ними
    start_idx = text.find('{')
    end_idx = text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx: end_idx + 1]

    return text.strip()


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
        # 1. Очищаем шаблон промпта от мусора перед использованием
        clean_template = clean_text_for_prompt(template_prompt)

        # Формируем финальный промпт
        final_prompt = clean_template.format(
            topic=topic, angle=angle, notes=notes)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                    "content": "Output ONLY valid JSON. No markdown, no extra text."},
                {"role": "user", "content": final_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        raw_content = response.choices[0].message.content

        # 2. Очищаем ответ AI перед парсингом
        cleaned_content = clean_json_response(raw_content)

        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Raw content was: {raw_content}")
            print(f"Cleaned content: {cleaned_content}")
            raise ValueError(
                f"AI returned invalid JSON even after cleaning: {cleaned_content[:100]}...")

    def generate(self, topic: str, angle: str, notes: str, languages: List[str],
                 system_instruction: str = None, structure_template: str = None) -> ArticleData:

        # --- ОЧИСТКА ВХОДНЫХ ДАННЫХ ---
        if structure_template:
            structure_template = clean_text_for_prompt(structure_template)
        if system_instruction:
            system_instruction = clean_text_for_prompt(system_instruction)

        base_system = "You are a viral TikTok historian and scriptwriter. You output ONLY valid JSON."
        plan_data = None
        plan_context = ""

        # Этап 1: Генерация плана (если есть шаблон)
        if structure_template:
            plan_data = self._generate_structure_plan(
                topic, angle, notes, structure_template)
            # Превращаем план в текст для контекста
            plan_context = f"\nSTRICT STRUCTURE TO FOLLOW:\n{json.dumps(plan_data)}\n"

        # Этап 2: Формирование системного промпта
        if system_instruction:
            system_prompt = f"{base_system}\n\nSTYLE INSTRUCTION: {system_instruction}"
        else:
            system_prompt = base_system

        # Этап 3: Формирование пользовательского промпта
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

        # Этап 4: Запрос к API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        # Этап 5: Очистка и парсинг ответа
        raw_content = response.choices[0].message.content
        cleaned_content = clean_json_response(raw_content)

        try:
            data = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse AI response as JSON. Cleaned content: {cleaned_content[:200]}")

        script_en = data.get('script_en', '')
        prompts = data.get('image_prompts', [])
        title = data.get('title', 'Untitled')
        hashtags = data.get('hashtags', '')

        # Этап 6: Переводы
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
        # 1. Очищаем шаблон промпта от мусора перед использованием
        clean_template = clean_text_for_prompt(template_prompt)

        # Формируем финальный промпт
        final_prompt = clean_template.format(
            topic=topic, angle=angle, notes=notes)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                    "content": "Output ONLY valid JSON. No markdown, no extra text."},
                {"role": "user", "content": final_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        raw_content = response.choices[0].message.content

        # 2. Очищаем ответ AI перед парсингом
        cleaned_content = clean_json_response(raw_content)

        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Raw content was: {raw_content}")
            print(f"Cleaned content: {cleaned_content}")
            raise ValueError(
                f"AI returned invalid JSON even after cleaning: {cleaned_content[:100]}...")

    def generate(self, topic: str, angle: str, notes: str, languages: List[str],
                 system_instruction: str = None, structure_template: str = None) -> ArticleData:

        # --- ОЧИСТКА ВХОДНЫХ ДАННЫХ ---
        if structure_template:
            structure_template = clean_text_for_prompt(structure_template)
        if system_instruction:
            system_instruction = clean_text_for_prompt(system_instruction)

        plan_data = None
        plan_context = ""

        # Этап 1: Генерация плана (если есть шаблон)
        if structure_template:
            plan_data = self._generate_structure_plan(
                topic, angle, notes, structure_template)
            plan_context = f"\nSTRICT STRUCTURE TO FOLLOW:\n{json.dumps(plan_data)}\n"

        # Этап 2: Формирование полного промпта для Gemini
        # Gemini лучше понимает инструкции, если они в одном блоке
        style_instr = f"\nSTYLE INSTRUCTION: {system_instruction}" if system_instruction else ""

        prompt_text = f"""
        You are a viral TikTok historian. Output ONLY valid JSON.
        {style_instr}

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

        # Этап 3: Запрос к API Gemini
        response = self.model.generate_content(prompt_text)
        raw_content = response.text

        # Этап 4: Очистка и парсинг ответа
        cleaned_content = clean_json_response(raw_content)

        try:
            data = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Gemini returned invalid JSON. Cleaned content: {cleaned_content[:200]}")

        script_en = data.get('script_en', '')
        prompts = data.get('image_prompts', [])
        title = data.get('title', 'Untitled')
        hashtags = data.get('hashtags', '')

        # Этап 5: Переводы
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
