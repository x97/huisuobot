"""主要做抽奖列表相关的handler"""
from django.utils import timezone
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler, CallbackContext
)


"""
抽奖列表主菜单（点击「抽奖列表」按钮触发）
"""


def show_lottery_menu(update: Update, context: CallbackContext):
    """显示抽奖管理二级菜单"""

    query = update.callback_query
    query.answer()

    # 结束所有对话
    from common.utils import end_all_conversations
    end_all_conversations(context)

    keyboard = [
        [InlineKeyboardButton("📢 发布抽奖", callback_data="admin_publish_lottery")],
        [InlineKeyboardButton("📋 抽奖列表", callback_data="list_lotteries")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(text="🎟️ 抽奖管理\n请选择操作：", reply_markup=reply_markup)


