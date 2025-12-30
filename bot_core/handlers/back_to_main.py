# bot_core/handlers/back_to_main.py

from telegram.ext import CallbackQueryHandler
from bot_core.handlers.common import back_to_main_common


def register_back_to_main(dp):
    """
    注册回到主菜单的回调处理器，回调数据为 back:main
    """
    dp.add_handler(CallbackQueryHandler(back_to_main_common, pattern=r"^(core:back_main|back:main)$"))
