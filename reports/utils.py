import logging
# 导入你的模型和已有函数
import re
from typing import List, Tuple
from typing import Optional

from django.conf import settings
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django_q.tasks import fetch
from telegram import Bot
from telegram import Message
from telegram.error import TelegramError

from reports.models import Report
from common.message_utils import queue_message  # 你的异步发送函数
from common.broadcast import send_broadcast_to_users

# 导入模型

logger = logging.getLogger(__name__)

# 初始化 Bot 实例
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)


def send_broadcast_to_admins(
        text: str,
        buttons: Optional[list] = None,
        disable_web_page_preview: bool = False,
        pin_message: bool = False,
        parse_mode: str = 'HTML'
) -> Tuple[int, int, List[str]]:
    from tgusers.models import TelegramUser
    admin_users = TelegramUser.objects.filter(is_admin=True)
    admin_user_ids = [admin.user_id for admin in admin_users]

    if not admin_user_ids:
        logger.warning("没有管理员用户，跳过广播")
        return (0, 0, [])

    logger.info(f"查询到 {len(admin_user_ids)} 名管理员，开始批量发送消息")

    try:
        return send_broadcast_to_users(
            user_ids=admin_user_ids,
            text=text,
            buttons=buttons,
            disable_web_page_preview=disable_web_page_preview,
            pin_message=pin_message,
            parse_mode=parse_mode
        )
    except Exception as e:
        logger.error(f"管理员广播失败: {e}", exc_info=True)
        return (0, len(admin_user_ids), [])

def send_to_report_center_and_group_async(report: Report):
    """异步发送消息到报告中心和原始群组"""
    content = report.content
    if not content:
        logger.warning(f"报告 {report.id} 无内容，跳过发送到报告中心/群组")
        return
    from mygroups.models import MyGroup

    # 提取群组链接
    match = re.search(r'(?:https?://)?t\.me/(\w+)', content)
    if not match:
        logger.warning(f"报告 {report.id} 内容中未找到有效群组链接：{content[:100]}...")
        return

    group_username = match.group(1)

    # 查询群组信息
    try:
        group_info = MyGroup.objects.get(group_username=group_username)
    except MyGroup.DoesNotExist:
        logger.warning(f"报告 {report.id} 未找到群组 '{group_username}' 的信息，跳过发送")
        return

    group_id = group_info.group_chat_id

    # 准备消息内容
    content_for_report = content
    content_for_group = f"✈️【收到新的报告】\n\n{content}"

    # 发送到报告中心
    if group_info.report_channel_id:
        try:
            task_id = queue_message(
                chat_id=group_info.report_channel_id,
                text=content_for_report,
                disable_web_page_preview=False,
                parse_mode='HTML'
            )
            logger.info(
                f"报告中心通知任务提交成功（report_id={report.id}, center_id={group_info.report_center_id}, task_id={task_id}）")
        except Exception as e:
            logger.error(f"报告中心通知任务提交失败（report_id={report.id}）：{str(e)}")

    # 发送到原始群组
    if group_id:
        try:
            task_id = queue_message(
                chat_id=group_id,
                text=content_for_group,
                disable_web_page_preview=False,
                parse_mode='HTML'
            )
            logger.info(f"原始群组通知任务提交成功（report_id={report.id}, group_id={group_id}, task_id={task_id}）")
        except Exception as e:
            logger.error(f"原始群组通知任务提交失败（report_id={report.id}）：{str(e)}")

# ---------------------- 审核通过相关通知 ----------------------
def send_approved_notification_to_user_async(report: Report):
    """异步发送「审核通过」通知给用户"""
    reporter = report.reporter
    if not reporter or not reporter.user_id:
        logger.warning(f"报告 {report.id} 无有效用户信息，跳过通过通知")
        return

    message_text = (
        f"🎉 你的报告（ID: {report.id}）已审核通过！\n"
        f"🎁 获得积分奖励：{report.point} 分\n"
        f"⭐ 获得经验奖励：200 经验"
    )

    # 异步发送 + 同步兜底
    try:
        task_id = queue_message(
            chat_id=reporter.user_id,
            text=message_text,
            disable_web_page_preview=False,
            parse_mode='HTML'
        )
        logger.info(f"通过通知任务提交成功（report_id={report.id}, user_id={reporter.user_id}, task_id={task_id}）")
    except Exception as e:
        try:
            bot.send_message(
                chat_id=reporter.user_id,
                text=message_text,
                disable_web_page_preview=False,
                parse_mode='HTML'
            )
            logger.warning(f"通过通知异步失败，已同步兜底（report_id={report.id}, error={str(e)}）")
        except Exception as e2:
            logger.error(f"通过通知同步兜底也失败（report_id={report.id}）：{str(e2)}", exc_info=True)

# ---------------------- 审核驳回相关通知 ----------------------
def send_rejected_notification_to_user_async(report: Report):
    """异步发送「审核驳回」通知给用户"""
    reporter = report.reporter
    if not reporter or not reporter.user_id:
        logger.warning(f"报告 {report.id} 无有效用户信息，跳过驳回通知")
        return

    # 提取驳回理由（review_note 存储拒绝原因）
    reject_reason = report.review_note or "未填写拒绝理由"

    message_text = (
        f"❌ 你的报告（ID: {report.id}）未通过审核\n"
        f"❓ 拒绝理由: {reject_reason}"
    )

    # 异步发送 + 同步兜底（和通过通知保持一致的可靠性）
    try:
        task_id = queue_message(
            chat_id=reporter.user_id,
            text=message_text,
            disable_web_page_preview=False,
            parse_mode='HTML'
        )
        logger.info(f"驳回通知任务提交成功（report_id={report.id}, user_id={reporter.user_id}, task_id={task_id}）")
    except Exception as e:
        # 异步失败时同步兜底
        try:
            bot.send_message(
                chat_id=reporter.user_id,
                text=message_text,
                disable_web_page_preview=False,
                parse_mode='HTML'
            )
            logger.warning(f"驳回通知异步失败，已同步兜底（report_id={report.id}, error={str(e)}）")
        except Exception as e2:
            logger.error(f"驳回通知同步兜底也失败（report_id={report.id}）：{str(e2)}", exc_info=True)
