# reports/services.py

import logging
import os
from typing import Tuple, Optional

from django.conf import settings
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils import timezone
from telegram import InlineKeyboardMarkup
from telegram import InputFile

from common.keyboards import single_button, append_back_button
from reports.keyboards import report_detail_buttons  # 如果你已实现该工厂

from reports.models import Report
from tgusers.models import TelegramUser


logger = logging.getLogger(__name__)

def get_report_photo(report: Report):
    """
    返回一个可用于 bot.send_photo 的文件对象（rb）。
    优先返回 report.image.path，否则返回项目占位图。
    调用者负责关闭文件句柄。
    """
    try:
        if report.image and hasattr(report.image, "path"):
            path = report.image.path
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return open(path, "rb")
    except Exception:
        pass

    fallback = os.path.join(settings.BASE_DIR, "static", "no_image.png")
    return open(fallback, "rb")


def approve_report(report: Report, admin_user: TelegramUser, reward_points: int):
    """
    执行审核通过的业务：更新 report 状态、发放积分、触发通知等。
    事务内执行，外层 handlers 也可在事务中调用。
    """
    with transaction.atomic():
        report.status = 'approved'
        report.point = reward_points
        report.reviewed_by = admin_user
        report.review_time = timezone.now()
        report.save(update_fields=['status', 'point', 'reviewed_by', 'review_time'])

        # 给提交者加积分（示例字段名）
        reporter = report.reporter
        if reporter:
            reporter.total_points = getattr(reporter, 'total_points', 0) + reward_points
            reporter.experience_points = getattr(reporter, 'experience_points', 0) + 200
            reporter.save(update_fields=['total_points', 'experience_points'])

        # 你可以在这里触发通知（post_save 信号或直接发送消息）


def reject_report(report: Report, admin_user: TelegramUser, reason: str):
    """
    执行审核不通过的业务：更新 report 状态、记录理由、触发通知等。
    """
    with transaction.atomic():
        report.status = 'rejected'
        report.review_note = reason
        report.reviewed_by = admin_user
        report.review_time = timezone.now()
        report.save(update_fields=['status', 'review_note', 'reviewed_by', 'review_time'])

        # 触发通知或其他后续处理


def render_report_detail(report_id: int,
                         include_admin_actions: bool = False,
                         requester_user_id: Optional[int] = None) -> Tuple[str, InlineKeyboardMarkup]:
    """
    返回 (detail_text, reply_markup)：
      - detail_text: 用于 edit_message_text 或 send_message 的 HTML 文本（已做简单转义/格式化）
      - reply_markup: InlineKeyboardMarkup（由 reports.keyboards.report_detail_buttons 生成）

    参数：
      - report_id: 报告 ID
      - include_admin_actions: 如果 True，会在按钮中包含管理员操作（通过/驳回）
      - requester_user_id: 发起请求的用户 id（可用于权限判断或定制按钮）

    使用示例：
      text, kb = render_report_detail(123, include_admin_actions=True, requester_user_id=admin_id)
      query.edit_message_text(text, reply_markup=kb, parse_mode='HTML')
    """
    try:
        report = Report.objects.get(id=report_id)
    except Report.DoesNotExist:
        return ("⚠️ 未找到该报告。", InlineKeyboardMarkup([[single_button("🔙 返回主菜单", "core", "back_main")]]))

    # reporter 信息
    reporter = report.reporter
    if reporter:
        reporter_display = f"@{reporter.username}" if getattr(reporter, "username", None) else f"用户ID: {reporter.user_id}"
    else:
        reporter_display = "未知用户"

    # 状态与备注
    status_display = report.get_status_display() if hasattr(report, "get_status_display") else report.status
    review_note = report.review_note or "无"
    points = getattr(report, "point", 0)

    # 时间格式
    created_at = report.created_at.strftime("%Y-%m-%d %H:%M") if getattr(report, "created_at", None) else "未知时间"
    review_time = report.review_time.strftime("%Y-%m-%d %H:%M") if getattr(report, "review_time", None) else "未审核"

    # 构建文本（使用 HTML 格式）
    # 注意：如果 report.content 可能包含 HTML 特殊字符，应在调用处或这里做转义。
    content = report.content or ""
    # 简单替换少量 HTML 特殊字符（若你项目已有更完善的转义工具可替换）
    def _escape_html(s: str) -> str:
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;"))

    content_escaped = _escape_html(content)

    text = (
        f"<b>📋 报告详情</b>\n\n"
        f"<b>🆔 报告ID:</b> {report.id}\n"
        f"<b>👤 提交者:</b> {_escape_html(reporter_display)}\n"
        f"<b>📅 提交时间:</b> {created_at}\n"
        f"<b>状态:</b> {status_display}\n"
        f"<b>积分:</b> {points}\n\n"
        f"<b>📝 报告内容:</b>\n{content_escaped}\n\n"
        f"<b>审核备注:</b> { _escape_html(review_note) }\n"
        f"<b>审核时间:</b> {review_time}\n"
    )

    # 生成按钮：优先使用 reports.keyboards.report_detail_buttons，如果不存在则回退到简单按钮
    try:
        kb = report_detail_buttons(report.id, include_admin_actions=include_admin_actions)
    except Exception:
        # 回退键盘：查看详情（无操作）、返回主菜单
        rows = [
            [single_button("🔎 查看详情", "reports", "view", report.id)]
        ]
        kb = append_back_button(rows)

    return text, kb
