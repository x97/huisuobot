from django.apps import AppConfig
import sys
import os


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

        # 检查是否在运行 bot
        # 假设 runbot 命令可能有参数，检查第一个参数
        is_running_bot = len(sys.argv) > 1 and sys.argv[1] == 'runbot'

        # 如果你在 runbot 中使用了 autoreload，可能需要检查 RUN_MAIN
        # 但这取决于你的 runbot 实现

        if is_running_bot:
            self._restore_lottery_jobs()

    def _restore_lottery_jobs(self):
        """恢复未开奖的任务"""
        try:
            from django.utils import timezone
            from lottery.models import Lottery
            from lottery.services.scheduler_service import add_lottery_draw_job

            active_lotteries = Lottery.objects.filter(end_time__gt=timezone.now(),is_drawn=False)

            for lottery in active_lotteries:
                add_lottery_draw_job(lottery)

            print(f"[Lottery] 已为 {active_lotteries.count()} 个进行中的抽奖恢复定时任务")

        except Exception as e:
            # 如果是数据库未就绪，静默失败
            if "no such table" in str(e).lower() or "does not exist" in str(e).lower():
                pass  # 表可能还没创建
            else:
                print(f"[Lottery] 恢复抽奖任务失败: {e}")