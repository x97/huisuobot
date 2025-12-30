# lottery/handlers/lottery_menu.py
# 抽奖管理二级菜单

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram import Update

from tgusers.services import update_or_create_user
from common.keyboards import append_back_button
from common.utils import end_all_conversations


from lottery.constant import PREFIX_USER, PREFIX_ADMIN


def show_lottery_menu(update: Update, context: CallbackContext):
    """显示抽奖管理二级菜单"""

    query = update.callback_query
    query.answer()

    # 管理员判断
    tguser = update_or_create_user(update.effective_user)
    if not tguser.is_admin:
        query.message.reply_text(
            "❌ 你不是管理员，无权使用此功能",
            reply_markup=append_back_button(None)
        )
        return

    # 结束所有对话（避免冲突）
    end_all_conversations(context)

    keyboard = [
        [InlineKeyboardButton("📢 发布抽奖", callback_data="lottery:admin:create")],
        [InlineKeyboardButton("📋 抽奖列表", callback_data="lottery:list:main")],
    ]
    reply_markup = append_back_button(keyboard)
    query.edit_message_text(
        text="🎟️ 抽奖管理\n请选择操作：",
        reply_markup=reply_markup
    )


def register_lottery_menu_handlers(dispatcher):
    dispatcher.add_handler(
        CallbackQueryHandler(show_lottery_menu, pattern=rf"^{PREFIX_ADMIN}:menu$")
    )
