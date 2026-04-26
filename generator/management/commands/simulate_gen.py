import json
import time
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

# Импорт моделей
from article.models import ArticleCluster, ArticleTranslation, ImagePrompt, Language, SceneType, Article
from topics.models import VideoProject
# Импортируем views как модуль
import article.views as article_views
import ai_inspector.services as ai_services


def add_session_to_request(request):
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


class Command(BaseCommand):
    help = 'Симуляция генерации статей без реального AI'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            '🚀 ЗАПУСК СИМУЛЯЦИИ ГЕНЕРАЦИИ СТАТЕЙ'))
        self.stdout.write('=' * 50)

        # 1. ОЧИСТКА
        self.stdout.write('🧹 Очистка тестовых данных...')
        VideoProject.objects.filter(topic="TEST_SIMULATION").delete()
        ArticleCluster.objects.filter(
            source_idea__topic="TEST_SIMULATION").delete()
        # Чистим промпты по ключевому слову
        ImagePrompt.objects.filter(prompt_text__icontains="Atlantis").delete()
        # Чистим статьи по ключевому слову
        Article.objects.filter(title__icontains="Atlantis").delete()

        # 2. СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ
        self.stdout.write('📝 Создание тестовой идеи...')
        test_idea = VideoProject.objects.create(
            topic="TEST_SIMULATION",
            angle="Тайны исчезнувшей цивилизации Атлантиды: факты и мифы",
            status="pending",
            notes="Тестовая идея для симуляции"
        )
        self.stdout.write(f'   ✅ Идея создана (ID: {test_idea.id})')

        try:
            lang_en = Language.objects.get(code='en')
            lang_ru = Language.objects.get(code='ru')
            lang_de = Language.objects.get(code='de')
            self.stdout.write('   ✅ Языки найдены: EN, RU, DE')
        except Language.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '   ❌ Ошибка: Не найдены языки в БД!'))
            return

        # 3. ПОДГОТОВКА ЗАПРОСА
        self.stdout.write('⚙️ Подготовка данных формы...')
        form_data = {
            'ai_provider': 'huggingface',
            'article_prompt': 'random',
            # Это поле теперь игнорируется в views, но оставим для формы
            'structure_plan': 'random',
            'languages': ['en', 'ru', 'de'],
            'idea_selection': [str(test_idea.id)],
            'image_mode': 'auto',
            'aspect_ratio': '9:16',
            'art_style': 'cinematic realistic',
            'manual_scene_count': 5,
            'generate_video': False,
            'enable_prompts_toggle': 'on'
        }

        factory = RequestFactory()
        request = factory.post('/article/api/start-generation/', form_data)
        request = add_session_to_request(request)

        self.stdout.write('   ✅ Данные формы подготовлены')

        # 4. ЗАПУСК С МОКИРОВАНИЕМ AI
        self.stdout.write('\n🤖 Запуск процесса генерации (с подменой AI)...')

        original_service_func = ai_services.generate_text
        original_view_func = article_views.generate_text

        def mock_generate_text(provider, prompt, max_tokens=2500):
            # 1. ПЕРЕВОД
            if "Translate" in prompt and ("Russian" in prompt or "German" in prompt or "Spanish" in prompt):
                lang = "Unknown"
                if "Russian" in prompt:
                    lang = "Russian"
                elif "German" in prompt:
                    lang = "German"
                elif "Spanish" in prompt:
                    lang = "Spanish"

                self.stdout.write(f'   🌍 [MOCK] Перевод на {lang}.')
                return json.dumps({
                    "title": f"Translated Title ({lang})",
                    "content": f"This is the translated content in {lang}. Original article was about Atlantis.",
                    "description": f"Translated description in {lang}. Short summary.",
                    "hashtags": f"#translated #{lang.lower()}"
                })

            # 2. СЦЕНЫ (ПРОМПТЫ)
            elif "visual scenes" in prompt or "image prompt" in prompt or "Split it into" in prompt:
                self.stdout.write(
                    '   🎨 [MOCK] Запрос на сцены! Возвращаем JSON.')
                return json.dumps([
                    {"scene_description": "Scene 1: Ancient ruins",
                        "prompt": "Ancient ruins of Atlantis, cinematic lighting --ar 9:16"},
                    {"scene_description": "Scene 2: Ocean depth",
                        "prompt": "Deep ocean with glowing crystals --ar 9:16"}
                ])

            # 3. ОСНОВНАЯ СТАТЬЯ
            else:
                self.stdout.write('   📝 [MOCK] Основная статья (EN).')
                return json.dumps({
                    "title": "The Mysteries of Atlantis: Facts and Myths",
                    "content": "Atlantis is a legendary island first mentioned by Plato... [Full Article Content about Atlantis]",
                    "description": "Discover the truth behind the legend of Atlantis.",
                    "hashtags": "#atlantis #history #mystery #facts #myth"
                })

        ai_services.generate_text = mock_generate_text
        article_views.generate_text = mock_generate_text

        session_key = request.session.session_key

        try:
            response = article_views.start_generation_api(request)
            result = json.loads(response.content)

            if result.get('status') == 'started':
                self.stdout.write('   ✅ Генерация запущена в фоне!')
                self.stdout.write('   ⏳ Ожидание (4 сек)...')

                wait_time = 0
                while wait_time < 4:
                    time.sleep(1)
                    wait_time += 1
                    progress = article_views.ARTICLE_GEN_PROGRESS.get(
                        session_key, {})
                    if progress.get('status') == 'done':
                        self.stdout.write(
                            f'   🎉 Процесс завершен: {progress.get("message")}')
                        break
                    elif progress.get('status') == 'error':
                        self.stdout.write(self.style.ERROR(
                            f'   ❌ Ошибка: {progress.get("message")}'))
                        break
            else:
                self.stdout.write(self.style.ERROR(
                    f'   ❌ Ошибка запуска: {result}'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'   ❌ Критическая ошибка: {e}'))
            import traceback
            traceback.print_exc()
            return
        finally:
            ai_services.generate_text = original_service_func
            article_views.generate_text = original_view_func

        # 5. ПРОВЕРКА РЕЗУЛЬТАТОВ В БД
        self.stdout.write('\n🔍 ПРОВЕРКА РЕЗУЛЬТАТОВ В БАЗЕ ДАННЫХ:')
        self.stdout.write('-' * 50)

        test_idea.refresh_from_db()
        if test_idea.status == 'completed':
            self.stdout.write(self.style.SUCCESS(
                '   ✅ Статус идеи: completed'))
        else:
            self.stdout.write(self.style.ERROR(
                f'   ❌ Статус идеи: {test_idea.status}'))

        clusters = ArticleCluster.objects.filter(source_idea=test_idea)
        if clusters.exists():
            cluster = clusters.first()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ ArticleCluster создан (ID: {cluster.id})'))

            translations = ArticleTranslation.objects.filter(cluster=cluster)
            self.stdout.write(
                f'   📄 Найдено переводов: {translations.count()}')

            expected_langs = ['en', 'ru', 'de']
            found_langs = [t.language.code for t in translations]

            # Словарь для хранения ID основной статьи (чтобы найти промпты)
            main_article_id = None

            for lang in expected_langs:
                if lang in found_langs:
                    t = translations.get(language__code=lang)
                    word_count = len(t.content.split())

                    # Проверка описания
                    has_desc = hasattr(
                        t, 'description') and bool(t.description)
                    desc_status = "✅" if has_desc else "❌ (Нет поля или пусто)"

                    self.stdout.write(self.style.SUCCESS(
                        f'      ✅ {lang.upper()}: "{t.title}" (Слов: {word_count}) [Описание: {desc_status}]'))

                    # Если это EN версия, попробуем найти основную статью (Article)
                    # Логика: основная статья должна иметь тот же title, что и EN перевод
                    if lang == 'en':
                        # Ищем статью с таким же заголовком
                        possible_articles = Article.objects.filter(
                            title=t.title)
                        if possible_articles.exists():
                            main_article_id = possible_articles.first().id
                            self.stdout.write(
                                f'         ↳ Найдена основная статья (Article ID: {main_article_id})')
                        else:
                            # Пробуем найти по части заголовка, если есть расхождения
                            possible_articles = Article.objects.filter(
                                title__icontains="Atlantis")
                            if possible_articles.exists():
                                main_article_id = possible_articles.first().id
                                self.stdout.write(
                                    f'         ↳ Найдена основная статья по частичному совпадению (ID: {main_article_id})')
                else:
                    self.stdout.write(self.style.ERROR(
                        f'      ❌ {lang.upper()}: ОТСУТСТВУЕТ'))

            # --- ПРОВЕРКА ПРОМПТОВ (ИСПРАВЛЕННАЯ) ---
            if 'enable_prompts_toggle' in form_data:
                if main_article_id:
                    test_prompts = ImagePrompt.objects.filter(
                        article_id=main_article_id)
                    if test_prompts.exists():
                        self.stdout.write(self.style.SUCCESS(
                            f'   🎨 Найдено промптов: {test_prompts.count()}'))
                        for p in test_prompts:
                            self.stdout.write(
                                f'      ✅ Промпт (ID: {p.id}): {p.prompt_text[:50]}...')
                    else:
                        self.stdout.write(self.style.ERROR(
                            '   ❌ Промпты НЕ найдены для этой статьи!'))
                        # Для отладки: покажем все промпты в БД с Atlantis
                        all_atlantis_prompts = ImagePrompt.objects.filter(
                            prompt_text__icontains="Atlantis")
                        if all_atlantis_prompts.exists():
                            self.stdout.write(
                                f'   ℹ️ Но найдено {all_atlantis_prompts.count()} промптов с "Atlantis" в других статьях!')
                            for p in all_atlantis_prompts:
                                self.stdout.write(
                                    f'      - Промпт ID: {p.id}, Привязан к Article ID: {p.article_id}')
                else:
                    self.stdout.write(self.style.ERROR(
                        '   ❌ Не удалось найти основную статью (Article) для проверки промптов.'))
                    # Фоллбэк: ищем любые промпты с Atlantis
                    fallback_prompts = ImagePrompt.objects.filter(
                        prompt_text__icontains="Atlantis")
                    if fallback_prompts.exists():
                        self.stdout.write(
                            f'   ℹ️ Найдено {fallback_prompts.count()} промптов вообще (без привязки к текущей проверке).')
            else:
                self.stdout.write(self.style.SUCCESS(
                    '   ✅ Промпты отключены, проверка пропущена'))

        else:
            self.stdout.write(self.style.ERROR(
                '   ❌ ArticleCluster НЕ создан!'))

        self.stdout.write('=' * 50)
        self.stdout.write(self.style.SUCCESS('🏁 СИМУЛЯЦИЯ ЗАВЕРШЕНА'))
