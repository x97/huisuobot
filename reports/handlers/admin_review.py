# reports/handlers/admin_review.py

import logging

from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    Filters,
)

from tgusers.models import TelegramUser
from reports.models import Report
from common.callbacks import make_cb
from common.keyboards import single_button, append_back_button
from reports import services

from .status_code import (
    REVIEWING_REPORT,
    INPUT_REPORT_POINTS,
    CONFIRM_APPROVAL,
    INPUT_REPORT_REASON,
    CONFIRM_REJECTION,
    INPUT_REPORT_PLACE
)

logger = logging.getLogger(__name__)

PREFIX = "reports"
CORE_BACK = ("core", "back_main")
REPORTS_PER_PAGE = 1


def _report_caption(report):
    reporter_info = f"@{report.reporter.username}" if getattr(report.reporter, "username", None) else f"用户ID: {report.reporter.user_id}"
    caption = (
        f"📋 待审核报告\n\n"
        f"🆔 报告ID: {report.id}\n"
        f"👤 提交者: {reporter_info}\n"
        f"📅 提交时间: {report.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"📝 报告内容:\n{report.content}\n\n"
    )
    return caption


def _report_page_keyboard(report_id: int, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    使用 common.single_button / make_cb 生成分页与审核按钮
    callback_data 采用 reports:... 命名空间
    最后通过 append_back_button 追加返回管理员菜单行
    """
    rows = []

    nav_row = []
    if current_page > 1:
        nav_row.append(single_button("⬅️ 上一页", PREFIX, "report_page", current_page - 1))
    if current_page < total_pages:
        nav_row.append(single_button("下一页 ➡️", PREFIX, "report_page", current_page + 1))
    if nav_row:
        rows.append(nav_row)

    # 审核操作行
    rows.append([
        single_button("✅ 通过", PREFIX, "approve_report", report_id),
        single_button("❌ 不通过", PREFIX, "reject_report", report_id),
    ])

    base_markup = InlineKeyboardMarkup(rows)
    # 使用 append_back_button 追加返回管理员菜单（保证回调格式一致）
    return append_back_button(base_markup)


def _reply_with_admin_back(context: CallbackContext, chat_id: int, text: str, base_markup: InlineKeyboardMarkup = None):
    """
    发送消息并确保带有返回管理员菜单按钮（用于回退场景）
    """
    markup = append_back_button(base_markup)
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


def send_paginated_reports(update: Update, context: CallbackContext, page_number: int = 1):
    """
    发送指定页的待审核报告（管理员入口）
    """
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id

    # 权限检查
    if not TelegramUser.objects.filter(user_id=user_id, is_admin=True).exists():
        if query:
            query.answer("你没有权限执行此操作。", show_alert=True)
        else:
            update.message.reply_text("你没有权限执行此操作。")
        return ConversationHandler.END

    reports_qs = Report.objects.filter(status='pending').order_by('-created_at')
    if not reports_qs.exists():
        # 使用 append_back_button 返回带返回管理员菜单的键盘
        empty_markup = append_back_button(None)
        if query:
            query.answer()
            try:
                query.edit_message_text(
                    "当前没有待审核的报告。",
                    reply_markup=empty_markup
                )
            except Exception:
                context.bot.send_message(chat_id=query.message.chat_id, text="当前没有待审核的报告。", reply_markup=empty_markup)
        else:
            update.message.reply_text("当前没有待审核的报告。")
        return ConversationHandler.END

    paginator = Paginator(reports_qs, REPORTS_PER_PAGE)
    try:
        page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page = paginator.page(1)

    report = page.object_list.first()
    caption = _report_caption(report)

    # 获取图片文件（由 services 封装）
    photo_file = services.get_report_photo(report)

    if query:
        query.answer()
        try:
            # 删除触发回调的消息（如果需要）
            try:
                query.delete_message()
            except Exception:
                pass

            context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_file,
                caption=caption,
                reply_markup=_report_page_keyboard(report.id, page.number, paginator.num_pages)
            )
        except Exception:
            # 回退为发送文本（避免抛错）
            _reply_with_admin_back(context, query.message.chat_id, caption)
    else:
        try:
            update.message.reply_photo(
                photo=photo_file,
                caption=caption,
                reply_markup=_report_page_keyboard(report.id, page.number, paginator.num_pages)
            )
        except Exception:
            update.message.reply_text(caption, reply_markup=_report_page_keyboard(report.id, page.number, paginator.num_pages))

    context.user_data['current_report_page'] = page.number
    return REVIEWING_REPORT


# 回调入口
def review_reports_callback(update: Update, context: CallbackContext):
    return send_paginated_reports(update, context)


def handle_page_navigation(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    # callback_data 格式 reports:report_page:<page>
    parts = query.data.split(":")
    if len(parts) < 3:
        query.answer("页码错误！", show_alert=True)
        return REVIEWING_REPORT
    try:
        page = int(parts[-1])
    except Exception:
        query.answer("页码错误！", show_alert=True)
        return REVIEWING_REPORT
    return send_paginated_reports(update, context, page_number=page)


# 审核通过流程
def handle_approval(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    # callback_data reports:approve_report:<id>
    parts = query.data.split(":")
    if len(parts) < 3:
        query.answer("报告ID错误！", show_alert=True)
        return REVIEWING_REPORT
    try:
        report_id = int(parts[-1])
    except Exception:
        query.answer("报告ID错误！", show_alert=True)
        return REVIEWING_REPORT

    if not Report.objects.filter(id=report_id, status='pending').exists():
        query.answer("该报告已被处理或不存在！", show_alert=True)
        return send_paginated_reports(update, context, page_number=context.user_data.get('current_report_page', 1))

    context.user_data['report_to_approve'] = report_id
    try:
        query.delete_message()
    except Exception:
        pass

    # 进入输入积分状态
    prompt = "/cancel 返回；请输入要奖励给用户的积分（仅支持整数）："
    try:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=prompt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=make_cb(PREFIX, "cancel_review"))]])
        )
    except Exception:
        # 回退为简单文本
        context.bot.send_message(chat_id=query.message.chat_id, text=prompt)
    return INPUT_REPORT_POINTS


def process_points(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    try:
        points = int(text)
        if points < 0:
            raise ValueError()
    except Exception:
        update.message.reply_text(
            "请输入非负整数积分。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 取消", callback_data=make_cb(PREFIX, "cancel_review"))]
            ])
        )
        return INPUT_REPORT_POINTS

    report_id = context.user_data.get('report_to_approve')
    try:
        report = Report.objects.get(id=report_id, status='pending')
    except Report.DoesNotExist:
        update.message.reply_text(
            "该报告已被处理或不存在。",
            reply_markup=InlineKeyboardMarkup([[single_button("📝 继续审核", PREFIX, "review_reports")]])
        )
        context.user_data.pop('report_to_approve', None)
        return ConversationHandler.END

    context.user_data['reward_points'] = points

    update.message.reply_text(
        "请输入会所名称：",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 取消", callback_data=make_cb(PREFIX, "cancel_review"))]
        ])
    )

    return INPUT_REPORT_PLACE

def process_report_place(update: Update, context: CallbackContext):
    place_name = update.message.text.strip()

    if not place_name:
        update.message.reply_text(
            "会所名称不能为空，请重新输入：",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 取消", callback_data=make_cb(PREFIX, "cancel_review"))]
            ])
        )
        return INPUT_REPORT_PLACE

    context.user_data['report_place_name'] = place_name

    report_id = context.user_data.get('report_to_approve')
    points = context.user_data.get('reward_points')

    confirmation_text = (
        f"请确认：\n\n"
        f"报告ID: {report_id}\n"
        f"奖励积分: {points}\n"
        f"会所名称: {place_name}\n\n"
        f"确认通过并发放积分？"
    )

    update.message.reply_text(
        confirmation_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 确认", callback_data=make_cb(PREFIX, "confirm_approval"))],
            [InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel_review"))]
        ])
    )

    return CONFIRM_APPROVAL


def confirm_approval_final(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    report_id = context.user_data.get('report_to_approve')
    reward_points = context.user_data.get('reward_points')
    place_name = context.user_data.get('report_place_name')

    if not all([report_id, reward_points, place_name]):
        try:
            query.edit_message_text("会话已过期，请重新审核。")
        except Exception:
            context.bot.send_message(chat_id=update.effective_chat.id, text="会话已过期，请重新审核。")
        return ConversationHandler.END

    try:
        with transaction.atomic():
            report = Report.objects.select_for_update().get(id=report_id, status='pending')
            admin_user = TelegramUser.objects.get(user_id=query.from_user.id)

            # 写入会所名称
            report.place_name = place_name

            # 调用你的业务逻辑（发积分、改状态等）
            services.approve_report(report, admin_user, reward_points)

            # 保存 place_name
            report.save(update_fields=["place_name"])

        success_markup = append_back_button(InlineKeyboardMarkup([
            [single_button("📝 继续审核", PREFIX, "review_reports")]
        ]))

        try:
            query.edit_message_text(
                f"✅ 操作成功！\n"
                f"报告ID: {report.id}\n"
                f"审核结果: 通过\n"
                f"奖励积分: {reward_points} 分\n"
                f"会所名称: {place_name}",
                reply_markup=success_markup
            )
        except Exception:
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ 操作成功！\n"
                     f"报告ID: {report.id}\n"
                     f"审核结果: 通过\n"
                     f"奖励积分: {reward_points} 分\n"
                     f"会所名称: {place_name}",
                reply_markup=success_markup
            )

    except Exception:
        logger.exception("confirm_approval_final failed")
        query.edit_message_text("❌ 操作失败，请稍后重试。")

    # 清理上下文
    for key in ['report_to_approve', 'reward_points', 'report_place_name']:
        context.user_data.pop(key, None)

    return ConversationHandler.END


# 审核不通过流程
def handle_rejection(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    parts = query.data.split(":")
    if len(parts) < 3:
        query.answer("报告ID错误！", show_alert=True)
        return REVIEWING_REPORT
    try:
        report_id = int(parts[-1])
    except Exception:
        query.answer("报告ID错误！", show_alert=True)
        return REVIEWING_REPORT

    if not Report.objects.filter(id=report_id, status='pending').exists():
        query.answer("该报告已被处理或不存在！", show_alert=True)
        return send_paginated_reports(update, context, page_number=context.user_data.get('current_report_page', 1))

    context.user_data['report_to_reject'] = report_id
    try:
        query.delete_message()
    except Exception:
        pass

    try:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="请输入报告不通过的理由：",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=make_cb(PREFIX, "cancel_review"))]])
        )
    except Exception:
        context.bot.send_message(chat_id=query.message.chat_id, text="请输入报告不通过的理由：")
    return INPUT_REPORT_REASON


def process_reject_reason(update: Update, context: CallbackContext):
    reason = update.message.text.strip()
    report_id = context.user_data.get('report_to_reject')
    if not reason:
        update.message.reply_text("拒绝理由不能为空，请重新输入。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=make_cb(PREFIX, "cancel_review"))]]))
        return INPUT_REPORT_REASON

    try:
        report = Report.objects.get(id=report_id, status='pending')
    except Report.DoesNotExist:
        update.message.reply_text("该报告已被处理或不存在。", reply_markup=InlineKeyboardMarkup([[single_button("📝 继续审核", PREFIX, "review_reports")]]))
        context.user_data.pop('report_to_reject', None)
        return ConversationHandler.END

    context.user_data['reject_reason'] = reason
    confirmation_text = (
        f"请确认：\n\n报告ID: {report.id}\n拒绝理由: {reason}\n\n确认不通过并通知用户？"
    )
    update.message.reply_text(
        confirmation_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 确认", callback_data=make_cb(PREFIX, "confirm_rejection"))],
            [InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel_review"))]
        ])
    )
    return CONFIRM_REJECTION


def confirm_rejection_final(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    report_id = context.user_data.get('report_to_reject')
    reason = context.user_data.get('reject_reason')

    if not all([report_id, reason]):
        try:
            query.edit_message_text("会话已过期，请重新审核。")
        except Exception:
            context.bot.send_message(chat_id=update.effective_chat.id, text="会话已过期，请重新审核。")
        return ConversationHandler.END

    try:
        with transaction.atomic():
            report = Report.objects.select_for_update().get(id=report_id, status='pending')
            admin_user = TelegramUser.objects.get(user_id=query.from_user.id)
            services.reject_report(report, admin_user, reason)

        success_markup = append_back_button(InlineKeyboardMarkup([
            [single_button("📝 继续审核", PREFIX, "review_reports")]
        ]))
        try:
            query.edit_message_text(
                f"✅ 操作成功！\n报告ID: {report.id}\n审核结果: 不通过\n拒绝理由: {reason}",
                reply_markup=success_markup
            )
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ 操作成功！\n报告ID: {report.id}\n审核结果: 不通过\n拒绝理由: {reason}", reply_markup=success_markup)
    except Report.DoesNotExist:
        try:
            query.edit_message_text("该报告已被处理或不存在。", reply_markup=InlineKeyboardMarkup([[single_button("📝 继续审核", PREFIX, "review_reports")]]))
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text="该报告已被处理或不存在。")
    except Exception:
        logger.exception("confirm_rejection_final failed")
        try:
            query.edit_message_text("❌ 操作失败，请稍后重试。", reply_markup=InlineKeyboardMarkup([[single_button("📝 继续审核", PREFIX, "review_reports")]]))
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text="❌ 操作失败，请稍后重试。")

    context.user_data.pop('report_to_reject', None)
    context.user_data.pop('reject_reason', None)
    return ConversationHandler.END


def cancel_review(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        query.answer()
        try:
            query.delete_message()
        except Exception:
            pass
        try:
            query.message.reply_text(
                "审核操作已取消！",
                reply_markup=append_back_button(InlineKeyboardMarkup([[single_button("📝 继续审核", PREFIX, "review_reports")]]))
            )
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text="审核操作已取消！", reply_markup=append_back_button(None))
    else:
        update.message.reply_text("审核操作已取消。", reply_markup=append_back_button(None))

    # 清理上下文
    keys = ['report_to_approve', 'reward_points', 'report_to_reject', 'reject_reason', 'current_report_page']
    for k in keys:
        context.user_data.pop(k, None)

    return ConversationHandler.END


def get_report_review_conversation_handler() -> ConversationHandler:
    """
    注意：对带参数的回调（page/id）使用带数字后缀的正则匹配
    - reports:review_reports
    - reports:report_page:<n>
    - reports:approve_report:<id>
    - reports:reject_report:<id>
    """
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(review_reports_callback, pattern=rf"^{PREFIX}:review_reports(?::\d+)?$")
        ],
        states={
            REVIEWING_REPORT: [
                CallbackQueryHandler(handle_page_navigation, pattern=rf"^{PREFIX}:report_page:\d+$"),
                CallbackQueryHandler(handle_approval, pattern=rf"^{PREFIX}:approve_report:\d+$"),
                CallbackQueryHandler(handle_rejection, pattern=rf"^{PREFIX}:reject_report:\d+$"),
            ],
            INPUT_REPORT_POINTS: [
                MessageHandler(Filters.text & ~Filters.command, process_points),
                CommandHandler('cancel', cancel_review),
                CallbackQueryHandler(cancel_review, pattern=rf"^{PREFIX}:cancel_review$"),
            ],
            INPUT_REPORT_PLACE: [
                MessageHandler(Filters.text & ~Filters.command, process_report_place),
                CommandHandler('cancel', cancel_review),
                CallbackQueryHandler(cancel_review, pattern=rf"^{PREFIX}:cancel_review$"),
            ],
            CONFIRM_APPROVAL: [
                CallbackQueryHandler(confirm_approval_final, pattern=rf"^{PREFIX}:confirm_approval$"),
                CallbackQueryHandler(cancel_review, pattern=rf"^{PREFIX}:cancel_review$"),
            ],
            INPUT_REPORT_REASON: [
                MessageHandler(Filters.text & ~Filters.command, process_reject_reason),
                CommandHandler('cancel', cancel_review),
                CallbackQueryHandler(cancel_review, pattern=rf"^{PREFIX}:cancel_review$"),
            ],
            CONFIRM_REJECTION: [
                CallbackQueryHandler(confirm_rejection_final, pattern=rf"^{PREFIX}:confirm_rejection$"),
                CallbackQueryHandler(cancel_review, pattern=rf"^{PREFIX}:cancel_review$"),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_review),
            CallbackQueryHandler(cancel_review, pattern=rf"^{PREFIX}:cancel_review$"),
        ],
        per_user=True,
        conversation_timeout=300,
    )


def register_admin_report_handlers(dispatcher):
    dispatcher.add_handler(get_report_review_conversation_handler())
