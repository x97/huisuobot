# ingestion/apps.py

from django.apps import AppConfig
import sys
import os


class IngestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingestion'

    def ready(self):
        """
        项目启动时自动创建 Django‑Q 定时任务
        但要避免 migrate、test、collectstatic 等命令重复执行
        """

        # 1. 排除不应执行的命令
        exclude_commands = {
            'migrate', 'makemigrations', 'showmigrations',
            'test', 'collectstatic'
        }
        current_commands = set(sys.argv)
        is_excluded = not current_commands.isdisjoint(exclude_commands)

        # 2. 仅在 Django 主进程启动时执行（避免 runserver autoreload 重复执行）
        if os.environ.get('RUN_MAIN') and not is_excluded:
            from .schedules import create_ingestion_schedule
            create_ingestion_schedule()
