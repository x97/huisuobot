import logging
from datetime import timedelta
from django.utils import timezone
from django_q.tasks import schedule
from django_q.models import Schedule
from .models import CarouselConfig
from .carousel_bot import carousel_bot

logger = logging.getLogger(__name__)


def get_task_name_prefix(config_id):
    return f"carousel_function_{config_id}"


def execute_carousel(config_id):
    """同步入口，供 Django-Q 调用"""
    try:
        config = CarouselConfig.objects.get(id=config_id, is_active=True)
    except CarouselConfig.DoesNotExist:
        logger.warning(f"[轮播任务] 配置不存在或未启用（ID:{config_id}）")
        return

    try:
        #尝试发送
        success, message_id = carousel_bot.send_carousel_message_sync(config)

        if success:
            config.last_sent_at = timezone.now()
            config.last_message_id = message_id
            config.total_sent_count += 1
            config.save(update_fields=["last_sent_at", "last_message_id", "total_sent_count", "updated_at"])
            #保存信息
            next_time = config.get_next_send_time()
        else:
            next_time = timezone.now() + timedelta(minutes=10)

        task_name = f"{get_task_name_prefix(config_id)}"
        Schedule.objects.update_or_create(
            name=task_name,
            defaults={
                "func": "tgfunc_carousel.tasks.execute_carousel",
                "args": str(config_id),
                "schedule_type": Schedule.ONCE,
                "next_run": next_time,
            }
        )
        logger.info(f"[轮播任务] 已排程下次任务：{task_name} → {next_time}")
    except Exception as e:
        logger.error(f"[轮播任务] 执行失败（ID:{config_id}）: {e}")
        next_time = timezone.now() + timedelta(minutes=10)
        task_name = f"{get_task_name_prefix(config_id)}"
        schedule(
            'tgfunc_carousel.tasks.execute_carousel',
            config_id,
            schedule_type=Schedule.ONCE,
            next_run=next_time,
            name=task_name,
        )
        logger.warning(f"[轮播任务] 发生错误，已安排重试：{task_name}")
