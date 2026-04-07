
# tasks.py

from django.db import transaction

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Lottery
from .services import draw_lottery_and_notify


@shared_task
def scan_and_draw_lottery():
    """
    每分钟扫描一次，找到到期但未开奖的 Lottery 并开奖
    """
    now = timezone.now()

    # 找到所有到期但未开奖、未取消的抽奖
    lotteries = Lottery.objects.filter(
        end_time__lte=now,
        is_drawn=False,
        is_active=True
    )

    for lottery in lotteries:
        process_single_lottery(lottery.id)



def process_single_lottery(lottery_id):
    """
    单个开奖逻辑，确保幂等 + 并发安全
    """

    with transaction.atomic():
        # 加行级锁，避免并发重复开奖
        lottery = Lottery.objects.select_for_update().get(id=lottery_id)

        # 幂等性检查
        if lottery.is_drawn or lottery.is_canceled:
            return

        # 执行开奖
        draw_lottery_and_notify(lottery.id)

        # 标记已开奖
        lottery.is_drawn = True
        lottery.save()





def add_lottery_draw_job(lottery):
    """
    （当前方案：无操作）

    说明：
        当前系统使用“方案一：每分钟扫描数据库”的方式进行开奖，
        因此不需要为每个 Lottery 动态创建调度任务。

        本函数被保留是为了保持业务层的统一接口。
        未来如果切换到其他调度方式（如 APScheduler、Celery ETA、Redis 延时队列），
        可以在此处实现真正的“添加定时任务”逻辑，而无需修改业务代码。

    参数：
        lottery: Lottery 实例，用于获取 id 和 end_time 等信息。

    当前行为：
        不执行任何操作，仅作为占位接口。
    """
    pass



def remove_lottery_draw_job(lottery_id):
    """
    （当前方案：无操作）

    说明：
        当前系统使用“方案一：每分钟扫描数据库”的方式进行开奖，
        Lottery 的取消逻辑只需要在数据库中标记 is_canceled=True，
        不需要删除任何调度任务。

        本函数被保留是为了保持业务层的统一接口。
        未来如果切换到其他调度方式（如 APScheduler、Celery ETA、Redis 延时队列），
        可以在此处实现真正的“删除定时任务”逻辑，而无需修改业务代码。

    参数：
        lottery_id: Lottery 主键 ID。

    当前行为：
        不执行任何操作，仅作为占位接口。
    """
    pass
