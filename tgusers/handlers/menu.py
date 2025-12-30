# tgusers/handlers/inheritance_handler.py

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
    CommandHandler,
)
from django.db import transaction
from tgusers.models import TelegramUser
from tgusers.keyboards import single_button, PREFIX_USER
from common.keyboards import append_back_button


logger = logging.getLogger(__name__)
# ==============================================================
# 1. 二级菜单：显示继承功能主菜单
# ==============================================================
def show_inheritance_menu(update: Update, context: CallbackContext) -> None:
    """显示继承功能的主菜单 (二级菜单)"""
    query = update.callback_query
    if query:
        query.answer()  # 对回调进行响应，避免加载动画

    user_id = update.effective_user.id
    try:
        user, created = TelegramUser.objects.get_or_create(user_id=user_id)

        if not user.inheritance_code:
            user.generate_inheritance_code()

        # --- 核心修改点 ---
        # 1. 使用 single_button 和规范的 callback_data
        keyboard_buttons = [
            [single_button("📋 复制继承码", PREFIX_USER, "copy_inheritance_code")],
            [single_button("🔄 刷新继承码", PREFIX_USER, "refresh_inheritance_code")],
            [single_button("👤 使用继承码", PREFIX_USER, "use_inheritance_code")],
        ]

        # 2. 使用 append_back_button 来添加统一的返回按钮
        reply_markup = append_back_button(keyboard_buttons)

        # 消息文本
        message_text = (
            "🔗 <b>继承功能</b>\n\n"
            "你可以将你的资产传承给其他用户。\n"
            "1. 点击下方按钮复制你的专属继承码。\n"
            "2. 让其他用户在「使用继承码」中输入此码即可继承你的资产。\n"
            "3. 继承后，你的资产将被清零，此码也会失效。\n\n"
            f"<code>{user.inheritance_code}</code>"
        )

        # 如果是第一次发送，用 send_message；如果是回调更新，用 edit_message_text
        if created or not query:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

    except Exception as e:
        logger.error(f"获取继承码失败: {e}")
        error_text = "❌ 获取继承码失败，请稍后再试。"
        if query:
            query.edit_message_text(text=error_text, reply_markup=append_back_button(None, prefix=PREFIX_USER))
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=error_text)

def register_inheritance_menu_handlers(dispatcher):
    """向 dispatcher 注册所有与继承相关的处理器"""

    # 注册入口和主要功能按钮的 CallbackQueryHandler
    dispatcher.add_handler(CallbackQueryHandler(
        show_inheritance_menu,
        pattern=rf"^{PREFIX_USER}:show_inheritance_menu$"
    ))