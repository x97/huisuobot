import logging
from django.utils import timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
)
from common.callbacks import make_cb
from common.keyboards import append_back_button
from mall.models import RedemptionRecord

logger = logging.getLogger(__name__)

PREFIX = "mall_admin"

WAITING_CODE = 8201
WAITING_CONFIRM = 8202


def admin_start_verify(update: Update, context: CallbackContext):
    """管理员点击核销商品入口"""
    q = update.callback_query
    q.answer()
    q.edit_message_text("请输入核销码：\n输入 /cancel 取消当前操作")
    return WAITING_CODE


def admin_input_code(update: Update, context: CallbackContext):
    """管理员输入核销码"""
    code = update.message.text.strip()
    try:
        redemption = RedemptionRecord.objects.get(verification_code=code, status="pending")
    except RedemptionRecord.DoesNotExist:
        update.message.reply_text("❌ 核销码不存在或已使用，请重新输入：\n输入 /cancel 取消当前操作")
        return WAITING_CODE

    context.user_data["verify_redemption_id"] = redemption.id
    summary = (
        f"请确认核销以下商品：\n\n"
        f"🎁 商品：{redemption.product.name}\n"
        f"👤 用户：{redemption.user.username}\n"
        f"🎟️ 核销码：{redemption.verification_code}\n\n"
        "✅确认核销吗？"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认核销", callback_data=make_cb(PREFIX, "confirm_verify")),
            InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel_verify")),
        ]
    ])
    update.message.reply_text(summary, reply_markup=keyboard)
    return WAITING_CONFIRM


def admin_confirm_verify(update: Update, context: CallbackContext):
    """确认核销商品"""
    q = update.callback_query
    q.answer()
    redemption_id = context.user_data.get("verify_redemption_id")

    try:
        redemption = RedemptionRecord.objects.get(id=redemption_id, status="pending")
        redemption.status = "used"
        redemption.verified_at = timezone.now()
        redemption.verified_by = update.effective_user.id
        redemption.save()
        q.edit_message_text(f"✅ 商品《{redemption.product.name}》核销成功！", reply_markup=append_back_button(None))
    except Exception as e:
        logger.error(f"核销失败: {e}")
        q.edit_message_text("❌ 核销失败！", reply_markup=append_back_button(None))

    return ConversationHandler.END


def admin_cancel_verify(update: Update, context: CallbackContext):
    """取消核销操作"""
    q = update.callback_query
    q.answer()
    q.edit_message_text("已取消核销。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_admin_verify_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_start_verify, pattern=r"^mall_admin:verify$"),
        ],
        states={
            WAITING_CODE: [MessageHandler(Filters.text, admin_input_code)],
            WAITING_CONFIRM: [
                CallbackQueryHandler(admin_confirm_verify, pattern=rf"^{PREFIX}:confirm_verify$"),
                CallbackQueryHandler(admin_cancel_verify, pattern=rf"^{PREFIX}:cancel_verify$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel_verify)],
    )


def register_admin_verify_handlers(dispatcher):
    dispatcher.add_handler(get_admin_verify_handler())
