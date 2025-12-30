# reports/handlers/user_report.py
from common.keyboards import append_back_button
import os
import logging
from datetime import datetime
from django.conf import settings
from django.db import transaction
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
)

from tgusers.services import update_or_create_user
from tgusers.models import TelegramUser
from reports.models import Report

from .status_code import (
    REPORT_WAITING_FOR_IMAGE,
    REPORT_WAITING_FOR_CONTENT,
    REPORT_WAITING_FOR_CONFIRMATION,
)

from reports.keyboards import confirm_cancel_buttons  # 使用按钮工厂
from common.callbacks import make_cb

logger = logging.getLogger(__name__)


def _ensure_media_path(date_obj: datetime):
    date_str = date_obj.strftime("%Y/%m/%d")
    rel_dir = os.path.join('report_images', date_str)
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    return rel_dir, abs_dir


def start_report(update: Update, context: CallbackContext) -> int:
    tg_user = update.effective_user
    if tg_user:
        update_or_create_user(tg_user)
        try:
            user_obj = TelegramUser.objects.filter(user_id=tg_user.id).first()
            if user_obj and not user_obj.has_interacted:
                user_obj.has_interacted = True
                user_obj.save(update_fields=["has_interacted"])
        except Exception:
            logger.exception("标记用户交互失败")

    prompt_text = (
        "请上传一张报告图片（预约记录或付款凭证等），图片为必填项。\n\n"
        "上传后会提示你输入报告内容。发送 /cancel 可随时取消。"
    )

    cancel_cb = make_cb("reports", "cancel_report")
    cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=cancel_cb)]])

    if update.callback_query:
        q = update.callback_query
        q.answer()
        try:
            q.edit_message_text(
                text=prompt_text,
                reply_markup=cancel_markup
            )
        except Exception:
            # 回退为发送新消息
            context.bot.send_message(chat_id=update.effective_chat.id, text=prompt_text, reply_markup=cancel_markup)
    else:
        update.message.reply_text(
            text=prompt_text,
            reply_markup=cancel_markup
        )

    return REPORT_WAITING_FOR_IMAGE


def handle_image(update: Update, context: CallbackContext) -> int:
    if not update.message or not update.message.photo:
        cancel_cb = make_cb("reports", "cancel_report")
        update.message.reply_text(
            "❌ 必须上传一张图片作为报告凭证，请重新上传。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=cancel_cb)]])
        )
        return REPORT_WAITING_FOR_IMAGE

    file_obj = update.message.photo[-1].get_file()
    context.user_data['report_image_file'] = file_obj

    cancel_cb = make_cb("reports", "cancel_report")
    update.message.reply_text(
        "✅ 图片已接收，请输入详细的报告内容（描述发生时间、地点、问题等）。",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=cancel_cb)]])
    )
    return REPORT_WAITING_FOR_CONTENT


def handle_content(update: Update, context: CallbackContext) -> int:
    if not update.message or not update.message.text:
        cancel_cb = make_cb("reports", "cancel_report")
        update.message.reply_text(
            "报告内容不能为空，请输入详细描述。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 取消", callback_data=cancel_cb)]])
        )
        return REPORT_WAITING_FOR_CONTENT

    text = update.message.text.strip()
    context.user_data['report_content'] = text

    preview = "📋 报告预览：\n"
    preview += f"内容：{text[:300]}{'...' if len(text) > 300 else ''}"

    # 使用 reports 的 confirm/cancel 按钮工厂
    update.message.reply_text(
        preview + "\n\n确认提交报告？",
        reply_markup=confirm_cancel_buttons()
    )
    return REPORT_WAITING_FOR_CONFIRMATION


def confirm_report(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query:
        query.answer("正在提交...")
    else:
        # 不应该发生，但兜底
        return ConversationHandler.END

    image_file = context.user_data.get('report_image_file')
    content = context.user_data.get('report_content')

    if not all([image_file, content]):
        # 使用 append_back_button 生成带返回主菜单的键盘
        back_markup = append_back_button(None)
        try:
            query.edit_message_text(
                "报告数据不完整，请重新提交。",
                reply_markup=back_markup
            )
        except Exception:
            context.bot.send_message(chat_id=update.effective_chat.id, text="报告数据不完整，请重新提交。", reply_markup=back_markup)

        context.user_data.pop('report_image_file', None)
        context.user_data.pop('report_content', None)
        return ConversationHandler.END

    try:
        with transaction.atomic():
            reporter_user, _ = TelegramUser.objects.get_or_create(user_id=query.from_user.id)
            if not reporter_user.has_interacted:
                reporter_user.has_interacted = True
                reporter_user.save(update_fields=["has_interacted"])

            report = Report.objects.create(
                reporter=reporter_user,
                content=content,
                status='pending',
                point=0
            )

            now = datetime.now()
            rel_dir, abs_dir = _ensure_media_path(now)
            image_filename = f"report_{report.id}_image.jpg"
            abs_path = os.path.join(abs_dir, image_filename)
            image_file.download(custom_path=abs_path)

            relative_image_path = os.path.join(rel_dir, image_filename)
            report.image = relative_image_path
            report.save(update_fields=["image"])

        # 构造包含返回主菜单的键盘（如果你还想保留其他按钮，可先构造 base_markup 再 append）
        success_markup = append_back_button(None)
        try:
            query.edit_message_text(
                "🎉 报告已成功提交！管理员将尽快审核你的报告。",
                reply_markup=success_markup
            )
        except Exception:
            context.bot.send_message(chat_id=update.effective_chat.id, text="🎉 报告已成功提交！管理员将尽快审核你的报告。", reply_markup=success_markup)

    except Exception as e:
        logger.exception("报告提交失败")
        error_markup = append_back_button(None)
        try:
            query.edit_message_text(
                f"❌ 报告提交失败：{str(e)}\n请稍后重试。",
                reply_markup=error_markup
            )
        except Exception:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ 报告提交失败：{str(e)}\n请稍后重试。", reply_markup=error_markup)

    context.user_data.pop('report_image_file', None)
    context.user_data.pop('report_content', None)
    return ConversationHandler.END


def cancel_report(update: Update, context: CallbackContext) -> int:
    context.user_data.pop('report_image_file', None)
    context.user_data.pop('report_content', None)

    back_markup = append_back_button(None)
    if update.callback_query:
        query = update.callback_query
        query.answer()
        try:
            query.edit_message_text(
                "报告提交已取消",
                reply_markup=back_markup
            )
        except Exception:
            context.bot.send_message(chat_id=update.effective_chat.id, text="报告提交已取消", reply_markup=back_markup)
    else:
        update.message.reply_text("报告提交已取消", reply_markup=back_markup)

    return ConversationHandler.END


# ConversationHandler 保持不变，但 entry 的 callback pattern 建议改为 reports:start_report
report_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_report, pattern=r"^reports:start_report$"),
        CommandHandler("submit_report", start_report),
    ],
    states={
        REPORT_WAITING_FOR_IMAGE: [
            MessageHandler(Filters.photo, handle_image),
            MessageHandler(Filters.text & ~Filters.command, handle_image),
        ],
        REPORT_WAITING_FOR_CONTENT: [
            MessageHandler(Filters.text & ~Filters.command, handle_content),
        ],
        REPORT_WAITING_FOR_CONFIRMATION: [
            CallbackQueryHandler(confirm_report, pattern=r"^reports:confirm_report$"),
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel_report),
        CallbackQueryHandler(cancel_report, pattern=r"^reports:cancel_report$"),
    ],
    allow_reentry=False,
    per_user=True,
)


def register_user_add_reporter(dispatcher):
    dispatcher.add_handler(report_conversation_handler)
