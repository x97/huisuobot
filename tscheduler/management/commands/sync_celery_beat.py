# tscheduler/management/commands/sync_celery_beat.py

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
import json

from tscheduler.beat import BEAT_SCHEDULE


class Command(BaseCommand):
    help = "Sync BEAT_SCHEDULE from tscheduler.beat into django-celery-beat database"

    def handle(self, *args, **kwargs):
        beat_schedule = BEAT_SCHEDULE

        if not beat_schedule:
            self.stdout.write(self.style.WARNING("No BEAT_SCHEDULE found"))
            return

        self.stdout.write(self.style.SUCCESS("Syncing Celery Beat tasks..."))

        for name, config in beat_schedule.items():
            task = config["task"]
            schedule = config["schedule"]

            # ===========================
            # 1. Interval schedule (秒)
            # ===========================
            if isinstance(schedule, (int, float)):
                interval, _ = IntervalSchedule.objects.get_or_create(
                    every=int(schedule),
                    period=IntervalSchedule.SECONDS,
                )
                periodic_task, created = PeriodicTask.objects.update_or_create(
                    name=name,
                    defaults={
                        "task": task,
                        "interval": interval,
                        "crontab": None,
                        "args": json.dumps([]),
                        "enabled": True,
                    },
                )

            # ===========================
            # 2. Crontab schedule
            # ===========================
            elif hasattr(schedule, "minute"):
                crontab, _ = CrontabSchedule.objects.get_or_create(
                    minute=schedule._orig_minute,
                    hour=schedule._orig_hour,
                    day_of_week=schedule._orig_day_of_week,
                    day_of_month=schedule._orig_day_of_month,
                    month_of_year=schedule._orig_month_of_year,
                    timezone="Asia/Shanghai",
                )
                periodic_task, created = PeriodicTask.objects.update_or_create(
                    name=name,
                    defaults={
                        "task": task,
                        "interval": None,
                        "crontab": crontab,
                        "args": json.dumps([]),
                        "enabled": True,
                    },
                )

            # ===========================
            # 3. 不支持的 schedule 类型
            # ===========================
            else:
                self.stdout.write(self.style.ERROR(f"Unsupported schedule type for {name}"))
                continue

            # 输出结果
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created task: {name}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated task: {name}"))

        self.stdout.write(self.style.SUCCESS("All Celery Beat tasks synced successfully!"))
