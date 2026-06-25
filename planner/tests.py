"""
Диагностический скрипт для проверки базы данных на нестыковки.
Запуск: python manage.py shell < planner/bd_test.py
"""

from planner.models import StoryPlan
from topics.models import ResearchProject
from collections import defaultdict


def check_database_integrity():
    """Проверяет целостность данных и находит нестыковки."""

    print("=" * 80)
    print("🔍 ДИАГНОСТИКА БАЗЫ ДАННЫХ")
    print("=" * 80)

    # 1. Общая статистика
    total_plans = StoryPlan.objects.count()
    total_research = ResearchProject.objects.count()

    print(f"\n СТАТИСТИКА:")
    print(f"   StoryPlan: {total_plans} записей")
    print(f"   ResearchProject: {total_research} записей")

    # 2. Все StoryPlan
    print(f"\n{'=' * 80}")
    print(" ВСЕ ОБЪЕКТЫ STORYPLAN:")
    print(f"{'=' * 80}")

    plans = StoryPlan.objects.select_related("research_project").order_by("-id")

    for plan in plans:
        print(f"\n StoryPlan ID={plan.id}")
        print(f"   Title: {plan.title}")
        print(f"   Status: {plan.status}")
        print(f"   Created: {plan.created_at}")

        if plan.research_project:
            print(f"   ResearchProject ID={plan.research_project.id}")
            print(f"   Research Topic: {plan.research_project.topic}")

            research_data = plan.research_project.research_data
            if isinstance(research_data, dict):
                topic_in_data = research_data.get("topic", "N/A")
                print(f"   Topic в research_data: {topic_in_data}")

                story_data = plan.story_data
                if isinstance(story_data, dict):
                    story_type = story_data.get("story_type", "N/A")
                    central_mystery = story_data.get("central_mystery", "N/A")[:100]
                    print(f"   Story Type: {story_type}")
                    print(f"   Central Mystery: {central_mystery}...")
        else:
            print(f"   ⚠️ ResearchProject: None (связь потеряна!)")

    # 3. Поиск дубликатов
    print(f"\n{'=' * 80}")
    print("🔎 ПОИСК ДУБЛИКАТОВ:")
    print(f"{'=' * 80}")

    plans_by_research = defaultdict(list)
    for plan in plans:
        if plan.research_project:
            plans_by_research[plan.research_project.id].append(plan)

    duplicates_found = False
    for research_id, related_plans in plans_by_research.items():
        if len(related_plans) > 1:
            duplicates_found = True
            print(
                f"\n⚠️ ДУБЛИКАТ: ResearchProject ID={research_id} имеет {len(related_plans)} StoryPlan:"
            )
            for p in related_plans:
                print(f"   - StoryPlan ID={p.id}, Title: {p.title}, Created: {p.created_at}")

    if not duplicates_found:
        print("✅ Дубликатов не найдено")

    # 4. Проверка конкретных ID (10 и 12)
    print(f"\n{'=' * 80}")
    print("🎯 ПРОВЕРКА КОНКРЕТНЫХ ID (10 и 12):")
    print(f"{'=' * 80}")

    for target_id in [10, 12]:
        try:
            plan = StoryPlan.objects.get(id=target_id)
            print(f"\n📖 StoryPlan ID={plan.id}")
            print(f"   Title: {plan.title}")
            print(f"   Status: {plan.status}")

            if plan.research_project:
                print(f"   ResearchProject ID={plan.research_project.id}")
                print(f"   Research Topic: {plan.research_project.topic}")

                story_data_str = str(plan.story_data)[:500]
                print(f"   Story Data (первые 500 символов): {story_data_str}...")
            else:
                print(f"   ⚠️ ResearchProject: None")

        except StoryPlan.DoesNotExist:
            print(f"\n❌ StoryPlan ID={target_id} не найден")

    # 5. Поиск "вакцины" в базе
    print(f"\n{'=' * 80}")
    print("💉 ПОИСК 'ВАКЦИНЫ' В БАЗЕ:")
    print(f"{'=' * 80}")

    vaccine_research = ResearchProject.objects.filter(topic__icontains="вакцин")

    if vaccine_research.exists():
        print(f"\n⚠️ Найдено {vaccine_research.count()} ResearchProject с темой 'вакцина':")
        for rp in vaccine_research:
            print(f"   ID={rp.id}, Topic: {rp.topic}")
            related_plans = rp.story_plans.all()
            if related_plans.exists():
                print(f"   Связанные StoryPlan: {related_plans.count()}")
                for p in related_plans:
                    print(f"      - ID={p.id}, Title: {p.title}")
    else:
        print("✅ ResearchProject с темой 'вакцина' не найдено")

    # 6. Поиск "Petra" в базе
    print(f"\n{'=' * 80}")
    print("🏛️ ПОИСК 'PETRA' В БАЗЕ:")
    print(f"{'=' * 80}")

    petra_research = ResearchProject.objects.filter(
        topic__icontains="petra"
    ) | ResearchProject.objects.filter(topic__icontains="петра")

    if petra_research.exists():
        print(f"\n✅ Найдено {petra_research.count()} ResearchProject с темой 'Petra':")
        for rp in petra_research:
            print(f"   ID={rp.id}, Topic: {rp.topic}")
            related_plans = rp.story_plans.all()
            if related_plans.exists():
                print(f"   Связанные StoryPlan: {related_plans.count()}")
                for p in related_plans:
                    print(f"      - ID={p.id}, Title: {p.title}, Status: {p.status}")
            else:
                print(f"   ️ Нет связанных StoryPlan")
    else:
        print("❌ ResearchProject с темой 'Petra' не найдено")

    print(f"\n{'=' * 80}")
    print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
    print(f"{'=' * 80}")


# 🔥 ЗАПУСК ФУНКЦИИ
check_database_integrity()
