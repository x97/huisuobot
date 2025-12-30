# collect/handlers/exchange_admin_appeal.py

import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    Filters,
)

from collect.models import ExchangeRecord
from tgusers.models import TelegramUser
from common.callbacks import make_cb
from common.keyboards import single_button, append_back_button

logger = logging.getLogger(__name__)

PREFIX = "admin_appeal"
CORE_BACK = ("core", "back_main")
PAGE_SIZE = 5

# Conversation states (only used for pagination view; actions are callback-driven)
REVIEWING_APPEALS = 1

# Helper: build keyboard for a page of appealed records
def _build_appeal_list_markup(records, page, total_pages):
    """
    records: list of ExchangeRecord for current page
    returns InlineKeyboardMarkup
    """
    rows = []
    for rec in records:
        # 每条记录显示一行简要信息 + 操作按钮行
        place_name = rec.place.name if rec.place else "已删除场所"
        created = rec.created_at.strftime("%Y-%m-%d")
        # 操作按钮：同意退回 / 驳回申诉
        approve_cb = make_cb(PREFIX, "approve", rec.id)
        reject_cb = make_cb(PREFIX, "reject", rec.id)
        rows.append([InlineKeyboardButton(f"ID:{rec.id} {place_name} {rec.points}分 {created}", callback_data=make_cb(PREFIX, "view", rec.id))])
        rows.append([
            InlineKeyboardButton("✅ 同意退回积分", callback_data=approve_cb),
            InlineKeyboardButton("❌ 驳回申诉", callback_data=reject_cb),
        ])

    # 分页导航
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb(PREFIX, "page", page - 1)))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=make_cb(PREFIX, "page", page + 1)))
    if nav:
        rows.append(nav)

    # 返回管理员菜单
    base = InlineKeyboardMarkup(rows)
    return append_back_button(base)


def _build_record_detail_text(rec: ExchangeRecord) -> str:
    place_name = rec.place.name if rec.place else "已删除场所"
    marketing_name = rec.marketing.name if rec.marketing else "无"
    created = rec.created_at.strftime("%Y-%m-%d %H:%M")
    lines = [
        f"兑换记录 ID: {rec.id}",
        f"用户: @{rec.user.username if rec.user and getattr(rec.user, 'username', None) else (str(rec.user.user_id) if rec.user else '未知')}",
        f"场所: {place_name}",
        f"营销: {marketing_name}",
        f"消耗积分: {rec.points}",
        f"状态: {rec.status}",
        f"兑换时间: {created}",
        f"申诉理由: {rec.appeal_reason or '无'}",
    ]
    return "\n".join(lines)


def _is_admin(user_id: int) -> bool:
    return TelegramUser.objects.filter(user_id=user_id, is_admin=True).exists()


# Entry: show appealed records page (page optional)
def admin_appeal_list(update: Update, context: CallbackContext, page: int = 1):
    query = update.callback_query
    if query:
        query.answer()
        caller_id = query.from_user.id
    else:
        caller_id = update.effective_user.id

    if not _is_admin(caller_id):
        if query:
            query.answer("你没有权限执行此操作。", show_alert=True)
        else:
            update.message.reply_text("你没有权限执行此操作。")
        return ConversationHandler.END

    qs = ExchangeRecord.objects.filter(status="appealed").order_by("-appeal_at", "-created_at")
    total = qs.count()
    if total == 0:
        text = "当前没有待处理的申诉记录。"
        if query:
            try:
                query.edit_message_text(text, reply_markup=append_back_button(None))
            except Exception:
                context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=append_back_button(None))
        else:
            update.message.reply_text(text)
        return ConversationHandler.END

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_records = list(qs[start:end])

    text_lines = [f"申诉列表（第 {page}/{total_pages} 页），共 {total} 条："]
    for rec in page_records:
        place_name = rec.place.name if rec.place else "已删除场所"
        created = rec.created_at.strftime("%Y-%m-%d")
        text_lines.append(f"ID:{rec.id} | {place_name} | {rec.points} 分 | {rec.user.user_id if rec.user else '未知'} | {created}")

    text = "\n".join(text_lines)
    markup = _build_appeal_list_markup(page_records, page, total_pages)

    try:
        if query:
            query.edit_message_text(text, reply_markup=markup)
        else:
            update.message.reply_text(text, reply_markup=markup)
    except Exception:
        if query:
            context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=markup)
        else:
            update.message.reply_text(text, reply_markup=markup)

    return REVIEWING_APPEALS


# View single record detail (optional)
def admin_view_record(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    query.answer()
    parts = query.data.split(":")
    try:
        rec_id = int(parts[-1])
    except Exception:
        query.answer("参数错误", show_alert=True)
        return

    if not _is_admin(query.from_user.id):
        query.answer("你没有权限执行此操作。", show_alert=True)
        return

    rec = ExchangeRecord.objects.filter(id=rec_id).first()
    if not rec:
        query.answer("记录不存在或已删除。", show_alert=True)
        return

    text = _build_record_detail_text(rec)
    # 操作按钮
    approve_cb = make_cb(PREFIX, "approve", rec.id)
    reject_cb = make_cb(PREFIX, "reject", rec.id)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 同意退回积分", callback_data=approve_cb),
         InlineKeyboardButton("❌ 驳回申诉", callback_data=reject_cb)],
        [InlineKeyboardButton("🔙 返回列表", callback_data=make_cb(PREFIX, "page", 1))]
    ])
    try:
        query.edit_message_text(text, reply_markup=append_back_button(markup))
    except Exception:
        context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=append_back_button(markup))


# Approve refund
def admin_approve_refund(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    query.answer()
    parts = query.data.split(":")
    try:
        rec_id = int(parts[-1])
    except Exception:
        query.answer("参数错误", show_alert=True)
        return ConversationHandler.END

    if not _is_admin(query.from_user.id):
        query.answer("你没有权限执行此操作。", show_alert=True)
        return ConversationHandler.END

    rec = ExchangeRecord.objects.select_for_update().filter(id=rec_id).first()
    if not rec:
        query.edit_message_text("记录不存在或已删除。")
        return ConversationHandler.END

    if rec.status == "refunded":
        query.edit_message_text("该记录已退回积分。")
        return ConversationHandler.END

    # Refund points transactionally
    try:
        with transaction.atomic():
            # refund to user if exists
            if rec.user:
                # reload user with select_for_update to avoid race
                user = TelegramUser.objects.select_for_update().get(id=rec.user.id)
                user.points = (user.points or 0) + rec.points
                user.save(update_fields=["points"])
            rec.status = "refunded"
            rec.refunded_at = timezone.now()
            rec.save(update_fields=["status", "refunded_at"])
    except Exception as e:
        logger.exception("refund failed for rec %s", rec_id)
        query.edit_message_text(f"退回积分失败：{str(e)}")
        return ConversationHandler.END

    # notify admin and user
    admin_text = f"已为记录 {rec.id} 退回 {rec.points} 分。"
    try:
        query.edit_message_text(admin_text, reply_markup=append_back_button(None))
    except Exception:
        context.bot.send_message(chat_id=query.message.chat_id, text=admin_text, reply_markup=append_back_button(None))

    # notify user if possible
    if rec.user and getattr(rec.user, "user_id", None):
        try:
            context.bot.send_message(chat_id=rec.user.user_id, text=f"你的申诉（记录ID:{rec.id}）已处理：管理员同意退回 {rec.points} 分，已到账。")
        except Exception:
            logger.exception("notify user failed for refund rec %s", rec.id)

    return ConversationHandler.END


# Reject appeal
def admin_reject_appeal(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    query.answer()
    parts = query.data.split(":")
    try:
        rec_id = int(parts[-1])
    except Exception:
        query.answer("参数错误", show_alert=True)
        return ConversationHandler.END

    if not _is_admin(query.from_user.id):
        query.answer("你没有权限执行此操作。", show_alert=True)
        return ConversationHandler.END

    rec = ExchangeRecord.objects.filter(id=rec_id).first()
    if not rec:
        query.edit_message_text("记录不存在或已删除。")
        return ConversationHandler.END

    # 驳回申诉：恢复为 completed（保留 appeal_reason/appeal_at）
    rec.status = "completed"
    rec.save(update_fields=["status"])

    try:
        query.edit_message_text(f"已驳回申诉，记录 {rec.id} 状态已恢复为 completed。", reply_markup=append_back_button(None))
    except Exception:
        context.bot.send_message(chat_id=query.message.chat_id, text=f"已驳回申诉，记录 {rec.id} 状态已恢复为 completed。", reply_markup=append_back_button(None))

    # notify user
    if rec.user and getattr(rec.user, "user_id", None):
        try:
            context.bot.send_message(chat_id=rec.user.user_id, text=f"你的申诉（记录ID:{rec.id}）已被驳回，积分未退回。")
        except Exception:
            logger.exception("notify user failed for reject rec %s", rec.id)

    return ConversationHandler.END


# Cancel / fallback
def admin_cancel(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        query.answer()
        try:
            query.edit_message_text("已取消。", reply_markup=append_back_button(None))
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text="已取消。", reply_markup=append_back_button(None))
    else:
        try:
            update.message.reply_text("已取消。")
        except Exception:
            pass
    return ConversationHandler.END


def get_admin_appeal_conversation_handler() -> ConversationHandler:
    """
    Conversation handlers for admin appeal review.
    Entry: admin_appeal:list or admin_appeal:page:<n>
    States: REVIEWING_APPEALS (mainly for keeping conversation alive)
    """
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: admin_appeal_list(u, c, page=1), pattern=rf"^{PREFIX}:list$"),
            CallbackQueryHandler(admin_appeal_list, pattern=rf"^{PREFIX}:page:\d+$"),
        ],
        states={
            REVIEWING_APPEALS: [
                CallbackQueryHandler(admin_view_record, pattern=rf"^{PREFIX}:view:\d+$"),
                CallbackQueryHandler(admin_approve_refund, pattern=rf"^{PREFIX}:approve:\d+$"),
                CallbackQueryHandler(admin_reject_appeal, pattern=rf"^{PREFIX}:reject:\d+$"),
                CallbackQueryHandler(admin_appeal_list, pattern=rf"^{PREFIX}:page:\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(admin_cancel, pattern=rf"^core:back_main$"),
            CommandHandler("cancel", admin_cancel),
        ],
        per_user=True,
    )
    return conv


def register_admin_appeal_handlers(dispatcher):
    dispatcher.add_handler(get_admin_appeal_conversation_handler())
    # also register direct callbacks so they work outside conversation context
    dispatcher.add_handler(CallbackQueryHandler(admin_approve_refund, pattern=rf"^{PREFIX}:approve:\d+$"))
    dispatcher.add_handler(CallbackQueryHandler(admin_reject_appeal, pattern=rf"^{PREFIX}:reject:\d+$"))
    dispatcher.add_handler(CallbackQueryHandler(admin_view_record, pattern=rf"^{PREFIX}:view:\d+$"))
    dispatcher.add_handler(CallbackQueryHandler(admin_appeal_list, pattern=rf"^{PREFIX}:list$"))
    dispatcher.add_handler(CallbackQueryHandler(admin_appeal_list, pattern=rf"^{PREFIX}:page:\d+$"))
