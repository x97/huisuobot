# lottery/services/scheduler_service.py

from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
from django.utils import timezone

from lottery.services.draw_service import draw_lottery_and_notify


# -------------------------
# 单例 scheduler（全局唯一）
# -------------------------
_scheduler = None


def get_scheduler():
    """返回全局唯一 scheduler，避免重复初始化"""
    global _scheduler

    if _scheduler is None:
        scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), 'default')

        try:
            scheduler.start()
            print("✅ APScheduler 启动成功（单例模式）")
        except Exception as e:
            print(f"❌ APScheduler 启动失败：{e}")
            scheduler.shutdown()

        _scheduler = scheduler

    return _scheduler


# -------------------------
# 添加开奖任务
# -------------------------
def add_lottery_draw_job(lottery):
    """添加开奖任务（自动使用单例 scheduler）"""
    scheduler = get_scheduler()  # 永远只会初始化一次

    run_time = lottery.end_time

    scheduler.add_job(
        func=draw_lottery_and_notify,
        args=(lottery.id,),
        trigger="date",
        run_date=run_time,
        id=f"lottery_draw_{lottery.id}",
        replace_existing=True
    )

    print(f"🎯 已添加开奖任务：{lottery.title} → {run_time}")
