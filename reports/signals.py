# report_handling/signals.py
import logging

from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from telegram import Bot

# 导入模型
from reports.models import Report
from .utils import (send_broadcast_to_admins, send_to_report_center_and_group_async,
                    send_rejected_notification_to_user_async)
from .utils import (send_approved_notification_to_user_async)

# 初始化 Bot 实例
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

logger = logging.getLogger(__name__)

# ==================== 报告提交信号 ====================
@receiver(post_save, sender=Report)
def handle_report_creation(sender, instance: Report, created: bool, **kwargs):
    """
    仅当新报告创建时（created=True），通知所有管理员有新报告待审核
    """
    if not created:
        return  # 只处理新建报告，状态更新不触发

    # 仅当新报告状态为 pending（默认值）时触发
    if instance.status != 'pending':
        return


    # 异步广播给所有管理员（复用你的 send_broadcast_to_admins）
    try:
        send_broadcast_to_admins(
            text="❤️❤️❤️❤️❤️❤️❤️❤️\n"
                 "您收到了一个新报告\n"
                 "请尽快去报告中心审批\n"
                 "审核通过后报告会自动发布到群里和报告中心\n",
            buttons=[{"📝 审核报告": "review_reports"}],
            disable_web_page_preview=True,
            parse_mode='Markdown'
        )
        logger.info(f"新报告 {instance.id} 的管理员通知已提交")
    except Exception as e:
        logger.error(f"新报告管理员通知发送失败（report_id={instance.id}）：{str(e)}", exc_info=True)

@receiver(pre_save, sender=Report)
def cache_old_status(sender, instance, **kwargs):
    if instance.pk:  # 已存在的对象
        try:
            instance._old_status = Report.objects.get(pk=instance.pk).status
        except Report.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Report)
def handle_report_status_change(sender, instance: Report, created: bool, update_fields, **kwargs):
    """
    Report 模型 post_save 信号接收器：
    1. 报告从 pending → approved：发送通过通知（用户/商家/报告中心/群组）
    2. 报告从 pending → rejected：发送驳回通知（仅用户）
    """
    # ========== 核心判断：仅处理「待审核→已处理」的场景 ==========
    if created:  # 新建报告不处理
        return
    from tgusers.models import TelegramUser

    # 提取当前状态和更新字段

    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    print("旧状态：", old_status)
    print("新状态：", new_status)

    if old_status == "pending" and new_status == "approved":
        try:
            logger.info(f"检测到报告审核通过（report_id={instance.id}），开始触发异步通知")
            # 1. 通知提交用户
            print(f"检测到报告审核通过（report_id={instance.id}），开始触发异步通知")
            send_approved_notification_to_user_async(instance)
                        # 3. 发送到报告中心和群组
            send_to_report_center_and_group_async(instance)
            logger.info(f"报告 {instance.id} 审核通过的异步通知任务已提交")

        except Exception as e:
            logger.error(f"处理报告通过通知失败（report_id={instance.id}）：{str(e)}", exc_info=True)

    # 场景2：审核驳回（pending → rejected）
    elif old_status == "pending" and new_status == "rejected":
        try:
            logger.info(f"检测到报告审核驳回（report_id={instance.id}），开始触发异步通知")
            # 仅通知提交用户（驳回无需通知商家/报告中心/群组）
            send_rejected_notification_to_user_async(instance)
            logger.info(f"报告 {instance.id} 审核驳回的异步通知任务已提交")
        except Exception as e:
            logger.error(f"处理报告驳回通知失败（report_id={instance.id}）：{str(e)}", exc_info=True)
