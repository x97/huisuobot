# /var/www/huisuobot/scheduler.py
import os
import django
import json
import pytz

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'huisuobot.settings')
django.setup()

from django.utils import timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJob
from lottery.models import Lottery
from lottery.services import draw_lottery_and_notify

TZ = pytz.timezone("Asia/Shanghai")

scheduler = BlockingScheduler(timezone=TZ)
scheduler.add_jobstore(DjangoJobStore(), "default")


# -------------------------
# 安全开奖包装器
# -------------------------
def safe_draw(lottery_id):
    try:
        lottery = Lottery.objects.get(id=lottery_id)

        if lottery.is_canceled:
            print(f"⏭️ Lottery {lottery_id} 已取消，跳过")
            return

        if lottery.is_drawn:
            print(f"⏭️ Lottery {lottery_id} 已开奖，跳过")
            return

        draw_lottery_and_notify(lottery_id)
        print(f"🎉 Lottery {lottery_id} 开奖成功")

    except Exception as e:
        print(f"❌ Lottery {lottery_id} 开奖失败: {e}")


# -------------------------
# 加载 + 补执行任务
# -------------------------
def load_and_recover_jobs():
    now = timezone.now().astimezone(TZ)
    print(f"🕒 [Scheduler] 刷新任务 - 当前时间: {now}")

    # 1. 补执行过期任务
    expired = Lottery.objects.filter(
        is_active=True,
        is_drawn=False,
        is_canceled=False,
        end_time__lte=now
    )

    for l in expired:
        print(f"⚠️ 补执行 lottery_id={l.id}")
        safe_draw(l.id)

    # 2. 从 DjangoJobStore 加载未来任务
    future_jobs = DjangoJob.objects.filter(
        id__startswith="lottery_draw_",
        next_run_time__gt=now
    )

    for job in future_jobs:
        try:
            job_state = json.loads(job.job_state)
            args = job_state.get("args", [])

            run_time = job.next_run_time.astimezone(TZ)

            if not scheduler.get_job(job.id):
                scheduler.add_job(
                    func=safe_draw,
                    args=args,
                    trigger=DateTrigger(run_date=run_time, timezone=TZ),
                    id=job.id,
                    replace_existing=True,
                    misfire_grace_time=300,
                    coalesce=True,
                )
                print(f"⏱️ 加载任务 {job.id} → {run_time}")

        except Exception as e:
            print(f"❌ 加载任务失败 {job.id}: {e}")

    # 打印当前任务
    for j in scheduler.get_jobs():
        print(f"📌 {j.id} → {j.next_run_time}")


# -------------------------
# 启动 scheduler
# -------------------------
def start_scheduler():
    print("🚀 启动 Scheduler...")

    load_and_recover_jobs()

    scheduler.add_job(
        func=load_and_recover_jobs,
        trigger=IntervalTrigger(minutes=1, timezone=TZ),
        id="refresh_jobs",
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
    )

    print("✅ Scheduler 启动成功")
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
