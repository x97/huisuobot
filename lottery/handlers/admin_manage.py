# lottery/handlers/admin_manage.py

from telegram.ext import CallbackQueryHandler
from lottery.handlers.lottery_menu import show_lottery_menu
from lottery.handlers.list_handlers import (
    show_lottery_list_main,
    handle_ongoing_lotteries,
    handle_ended_lotteries,
    handle_lottery_pagination,
    confirm_cancel_lottery,
    do_cancel_lottery,
    cancel_cancel,
)


def register_admin_manage_handlers(dp):

    # 一级菜单入口（主菜单 → 抽奖管理）
    dp.add_handler(CallbackQueryHandler(
        show_lottery_menu,
        pattern=r"^lottery:menu$"
    ))

    # 二级菜单：抽奖列表主菜单
    dp.add_handler(CallbackQueryHandler(
        show_lottery_list_main,
        pattern=r"^lottery:list:main$"
    ))

    # 正在进行
    dp.add_handler(CallbackQueryHandler(
        handle_ongoing_lotteries,
        pattern=r"^lottery:list:ongoing:\d+$"
    ))

    # 已结束
    dp.add_handler(CallbackQueryHandler(
        handle_ended_lotteries,
        pattern=r"^lottery:list:ended:\d+$"
    ))

    # 分页
    dp.add_handler(CallbackQueryHandler(
        handle_lottery_pagination,
        pattern=r"^lottery:list:(ongoing|ended):\d+$"
    ))

    # 取消抽奖（确认）
    dp.add_handler(CallbackQueryHandler(
        confirm_cancel_lottery,
        pattern=r"^lottery:cancel:confirm:\d+$"
    ))

    # 执行取消
    dp.add_handler(CallbackQueryHandler(
        do_cancel_lottery,
        pattern=r"^lottery:cancel:do$"
    ))

    # 返回
    dp.add_handler(CallbackQueryHandler(
        cancel_cancel,
        pattern=r"^lottery:cancel:back$"
    ))
