# ingestion/schedules.py

from django_q.models import Schedule


def create_ingestion_schedule():
    """
    创建 ingestion 定时任务（如果不存在）
    每 20 分钟执行一次 run_ingestion
    """

    # 如果已存在同名任务 → 不创建
    if Schedule.objects.filter(name="Ingestion every 20 minutes").exists():
        print("⏩ Django‑Q ingestion 任务已存在，跳过创建")
        return

    # 创建任务
    Schedule.objects.create(
        name="Ingestion every 20 minutes",
        func="django.core.management.call_command",
        args="run_ingestion",
        schedule_type=Schedule.MINUTES,
        minutes=20,
        repeats=-1,
    )

    print("✅ 已创建 Django‑Q ingestion 定时任务（每 20 分钟）")
