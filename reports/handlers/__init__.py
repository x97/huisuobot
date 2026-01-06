# reports/handlers.py

from telegram.ext import CallbackQueryHandler
from common.callbacks import parse_cb
from tgusers.models import TelegramUser
from reports.services import approve_report, reject_report, render_report_detail
from .user_report import start_report, confirm_report, cancel_report  # 复用对话函数
from .user_report import register_user_add_reporter
from .user_reporets_list import register_reports_list_handlers
from .admin_review import register_admin_report_handlers
from .report_query import register_report_handlers

def reports_callback_router(update, context):
    query = update.callback_query
    prefix, action, args = parse_cb(query.data)

    if prefix != "reports":
        return

    user_id = query.from_user.id
    try:
        user = TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        query.answer("未注册用户")
        return

    # 对话相关 action 直接委托给 user_report 模块
    if action == "start_report":
        start_report(update, context)
        return

    if action == "confirm_report":
        # 直接调用对话中的确认提交（如果是对话内触发）
        confirm_report(update, context)
        return

    if action == "cancel_report":
        cancel_report(update, context)
        return

    # 管理员操作
    if action == "approve":
        if not user.is_admin:
            query.answer("无权限")
            return
        report_id = args[0] if args else None
        approve_report(report_id, reviewer_user_id=user_id)
        query.edit_message_text("已通过该报告")
        return

    if action == "reject":
        if not user.is_admin:
            query.answer("无权限")
            return
        report_id = args[0] if args else None
        reject_report(report_id, reviewer_user_id=user_id)
        query.edit_message_text("已驳回该报告")
        return

    if action == "view":
        report_id = args[0] if args else None
        text = render_report_detail(report_id)
        query.edit_message_text(text)
        return



def register_report_handlers(dispatcher):
    register_user_add_reporter(dispatcher)
    register_reports_list_handlers(dispatcher)
    register_admin_report_handlers(dispatcher)
    register_report_handlers(dispatcher)
