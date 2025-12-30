import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
from common.callbacks import make_cb
from common.keyboards import append_back_button
from mall.models import RedemptionRecord
from tgusers.services import update_or_create_user
logger = logging.getLogger(__name__)

PREFIX = "mall_user"

WAITING_HISTORY = 8501
PAGE_SIZE = 5


def user_start_history(update: Update, context: CallbackContext, page: int = 1):
    """用户点击兑换历史入口"""
    q = update.callback_query
    q.answer()
    user = update_or_create_user(update.effective_user)
    records = RedemptionRecord.objects.filter(user=user).order_by("-redeemed_at")
    total = records.count()
    if total == 0:
        q.edit_message_text("暂无兑换记录。", reply_markup=append_back_button(None))
        return ConversationHandler.END

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    current_records = records[start_idx:end_idx]

    text = f"📜 我的兑换记录（第{page}/{total_pages}页）\n\n"
    for r in current_records:
        status_text = {"pending": "⏳ 待核销", "used": "✅ 已核销", "expired": "❌ 已过期"}[r.status]
        cost = f"{r.product.points_needed}积分" if r.product.points_needed > 0 else f"{r.product.coins_needed}金币"
        text += (
            f"商品：{r.product.name}\n"
            f"消耗：{cost}\n"
            f"状态：{status_text}\n"
            f"核销码：{r.verification_code}\n"
            f"时间：{r.redeemed_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    # 构造分页按钮
    keyboard = []
    if total_pages > 1:
        row = []
        if page > 1:
            row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb(PREFIX, "history", page - 1)))
        if page < total_pages:
            row.append(InlineKeyboardButton("➡️ 下一页", callback_data=make_cb(PREFIX, "history", page + 1)))
        if row:
            keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 返回商城菜单", callback_data=make_cb(PREFIX, "menu"))])

    q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_HISTORY


def user_back_history(update: Update, context: CallbackContext):
    """用户返回商城菜单"""
    q = update.callback_query
    q.answer()
    q.edit_message_text("已返回商城菜单。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_user_history_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_start_history, pattern=r"^mall_user:history$"),
        ],
        states={
            WAITING_HISTORY: [
                CallbackQueryHandler(
                    lambda u, c: user_start_history(u, c, int(u.callback_query.data.split(":")[-1])),
                    pattern=rf"^{PREFIX}:history:\d+$"
                ),
                CallbackQueryHandler(user_back_history, pattern=rf"^{PREFIX}:menu$"),
            ],
        },
        fallbacks=[],
    )


def register_user_history_handlers(dispatcher):
    dispatcher.add_handler(get_user_history_handler())
