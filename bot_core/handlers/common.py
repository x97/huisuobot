# bot_core/handlers/common.py

#在任何命令执行前更新用户信息

from telegram import Update
from telegram.ext import CallbackContext
from tgusers.services import update_or_create_user
from bot_core.keyboards.main_menus import (
    admin_main_menu,
    merchant_main_menu,
    user_main_menu,
)

def pre_process_user(update, context):
    if update.effective_user:
        update_or_create_user(update.effective_user)

def back_to_main_common(update: Update, context: CallbackContext) -> None:
    """
    通用的“返回主菜单”处理逻辑。
    可在多个 handlers 中复用。
    """
    query = update.callback_query
    if not query:
        return

    # 回应回调，避免客户端一直显示加载
    try:
        query.answer()
    except Exception:
        pass

    tg_user = query.from_user
    user = update_or_create_user(tg_user)

    # 根据用户角色选择不同的主菜单
    if getattr(user, "is_admin", False):
        text = "返回管理员主菜单"
        reply_markup = admin_main_menu()
    elif getattr(user, "is_merchant", False):
        text = "返回商家主菜单"
        reply_markup = merchant_main_menu()
    else:
        text = "返回主菜单"
        reply_markup = user_main_menu()

    # 尝试编辑消息，失败则发送新消息
    try:
        query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        try:
            context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
        except Exception:
            # 最后兜底：忽略或记录日志（这里不引入 logger，按需添加）
            pass
