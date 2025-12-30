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
from mall.models import MallProduct

logger = logging.getLogger(__name__)

PREFIX = "mall_user"

WAITING_LIST = 8401


PAGE_SIZE = 5

def user_start_list(update: Update, context: CallbackContext, page: int = 1):
    q = update.callback_query
    q.answer()

    products = MallProduct.objects.filter(is_active=True, stock__gt=0).order_by("-id")
    total = products.count()
    if total == 0:
        q.edit_message_text("暂无可兑换商品。", reply_markup=append_back_button(None))
        return ConversationHandler.END

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    current_products = products[start_idx:end_idx]

    text = f"🎁 可兑换商品列表（第{page}/{total_pages}页）：\n"
    keyboard = []
    for p in current_products:
        text += f"{p.id}. {p.name} - {p.cost_text()} - 库存:{p.stock}\n"
        keyboard.append([
            InlineKeyboardButton(f"兑换 {p.name}", callback_data=make_cb(PREFIX, "redeem", p.id))
        ])

    # 分页按钮
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb(PREFIX, "list", page - 1)))
    if page < total_pages:
        row.append(InlineKeyboardButton("➡️ 下一页", callback_data=make_cb(PREFIX, "list", page + 1)))
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 返回商城菜单", callback_data=make_cb(PREFIX, "menu"))])

    q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_LIST


def user_back_list(update: Update, context: CallbackContext):
    """用户返回商城菜单"""
    q = update.callback_query
    q.answer()
    q.edit_message_text("已返回商城菜单。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_user_list_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_start_list, pattern=r"^mall_user:list$"),
        ],
        states={
            WAITING_LIST: [
                CallbackQueryHandler(
                    lambda u, c: user_start_list(u, c, int(u.callback_query.data.split(":")[-1])),
                    pattern=rf"^{PREFIX}:list:\d+$"
                ),
                CallbackQueryHandler(user_back_list, pattern=rf"^{PREFIX}:menu$"),
            ],

        },
        fallbacks=[],
    )


def register_user_list_handlers(dispatcher):
    dispatcher.add_handler(get_user_list_handler())
