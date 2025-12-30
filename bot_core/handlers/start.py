# bot_core/handlers/start.py

from telegram.ext import CommandHandler
from tgusers.services import update_or_create_user, mark_user_interacted
from .common import pre_process_user
from bot_core.keyboards.main_menus import (
    admin_main_menu,
    merchant_main_menu,
    user_main_menu,
)


def start_handler(update, context):
    tg_user = update.effective_user
    user = update_or_create_user(tg_user)
    mark_user_interacted(user)

    if user.is_admin:
        update.message.reply_text("欢迎回来，管理员。", reply_markup=admin_main_menu())
        return

    if user.is_merchant:
        update.message.reply_text("欢迎回来，商家用户。", reply_markup=merchant_main_menu())
        return

    update.message.reply_text("欢迎使用本机器人。", reply_markup=user_main_menu())


def register_start_handlers(dp):
    dp.add_handler(CommandHandler("start", start_handler))
