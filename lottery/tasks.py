

# -------------------------
# 添加开奖任务
# -------------------------
from django_apscheduler.models import DjangoJob

from apscheduler.triggers.date import DateTrigger
from django.utils import timezone
import pytz
import json

TZ = pytz.timezone("Asia/Shanghai")

def add_lottery_draw_job(lottery):
    job_id = f"lottery_draw_{lottery.id}"
    run_time = lottery.end_time.astimezone(TZ)

    # 删除旧任务
    DjangoJob.objects.filter(id=job_id).delete()

    # APScheduler job_state
    job_state = {
        "version": 1,
        "jobstore": "default",
        "executor": "default",
        "func": "lottery.draw.safe_draw",
        "args": [lottery.id],
        "kwargs": {},
        "trigger": {
            "type": "date",
            "run_date": run_time.isoformat(),
            "timezone": "Asia/Shanghai"
        }
    }

    DjangoJob.objects.create(
        id=job_id,
        next_run_time=run_time,
        job_state=json.dumps(job_state)
    )

    print(f"🎯 已写入 DjangoJobStore：{job_id} → {run_time}")



def remove_lottery_draw_job(lottery_id):
    job_id = f"lottery_draw_{lottery_id}"

    deleted, _ = DjangoJob.objects.filter(id=job_id).delete()

    if deleted:
        print(f"⏹️ 已从 DjangoJobStore 删除任务：{job_id}")
        return True
    else:
        print(f"ℹ️ 任务不存在：{job_id}")
        return False
