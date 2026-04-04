import sys

from django.apps import AppConfig
from django.utils import timezone



class LotteryConfig(AppConfig):
    name = "lottery"
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        在 bot 运行时恢复抽奖任务
        """
        # 跳过数据库操作相关的命令
        skip_commands = {'migrate', 'makemigrations', 'test'}
        if len(sys.argv) > 1 and sys.argv[1] in skip_commands:
            return
