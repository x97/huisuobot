# tscheduler/beat.py

from celery.schedules import crontab

# Celery Beat 定时任务配置（统一管理）
BEAT_SCHEDULE = {
    # ===========================
    # 1. 每 20 分钟 ingestion 任务
    # ===========================
    "ingestion-every-20-minutes": {
        "task": "tscheduler.tasks.celery_run_ingestion_pipeline",
        "schedule": 20 * 60,  # 每 20 分钟
    },

    # ===========================
    # 2. 每分钟扫描开奖任务（方案一）
    # ===========================
    "scan-lottery-every-minute": {
        "task": "lottery.tasks.scan_and_draw_lottery",
        "schedule": 60.0,  # 每 60 秒执行一次
    },

    "broadcast-campaigns-every-hour": {
        "task": "collect.tasks.broadcast_campaigns_to_all_groups",
        "schedule": 3600,  # 每小时
    },
}
