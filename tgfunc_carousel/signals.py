import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django_q.tasks import schedule
from django_q.models import Schedule
from django.core.exceptions import ValidationError
from .models import CarouselConfig
from .tasks import get_task_name_prefix

logger = logging.getLogger(__name__)

def safe_delete_function_tasks(config_id):
    try:
        task_prefix = get_task_name_prefix(config_id)
        tasks = Schedule.objects.filter(name=task_prefix)
        count = tasks.count()
        tasks.delete()
        logger.info(f"[轮播任务] 已删除 {count} 个任务（ID:{config_id}）")
        return count
    except Exception as e:
        logger.error(f"[轮播任务] 删除任务失败（ID:{config_id}）: {e}")
        return 0

def _validate_data_fetcher(instance: CarouselConfig):
    """保存時快速驗證 data_fetcher 返回類型"""
    try:
        func = instance.get_data_fetcher()
        result = func(1, instance.page_size)
        if not (isinstance(result, tuple) and len(result) == 2):
            raise ValidationError("data_fetcher 必須返回 (text, total_pages)")
    except Exception as e:
        raise ValidationError(f"data_fetcher 無效: {e}")


@receiver(post_save, sender=CarouselConfig)
def handle_carousel_config_save(sender, instance, created, **kwargs):
    """保存時註冊一次性任務（首次）"""
    # 清理舊任務避免重覆
    safe_delete_function_tasks(instance.id)

    # 驗證 data_fetcher
    _validate_data_fetcher(instance)

    if instance.is_active:
        first_send_time = instance.get_next_send_time()
        task_name = f"{instance.get_task_name_prefix()}"

        schedule(
            'tgfunc_carousel.tasks.execute_carousel',
            instance.id,
            schedule_type=Schedule.ONCE,
            next_run=first_send_time,
            name=task_name,
        )
        logger.info(f"[輪播任務] 配置「{instance.name}」已啟用，首次發送時間：{first_send_time}")
    else:
        logger.info(f"[輪播任務] 配置「{instance.name}」已禁用，所有定時任務已刪除")


@receiver(pre_delete, sender=CarouselConfig)
def handle_carousel_config_delete(sender, instance, **kwargs):
    """刪除時清理所有任務"""
    safe_delete_function_tasks(instance.id)
    logger.info(f"[輪播任務] 配置「{instance.name}」（ID:{instance.id}）已刪除，關聯任務已清理")
