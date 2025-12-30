# bot_core/keyboards/main_menus.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from reports.keyboards import user_submit_report_button_row, my_reports_entry_button_row, admin_review_entry_row
from collect.keyboards import exchange_start_button_row, exchange_history_button_row, admin_review_appeals_button_row
from collect.keyboards import (admin_review_reward_button_row, admin_publish_reward_button_row,
                               admin_reward_list_button_row,user_my_submissions_button_row,
                               admin_create_staff_button_row)
from tgusers.keyboards import user_profile_button_row, admin_adjust_user_button_row,user_inheritance_entry_row
from mall.keyboards import user_mall_entry_row, admin_mall_entry_row
from lottery.keyboards import lottery_admin_entry_row, lottery_user_wins_entry_row


def admin_main_menu():
    keyboard = [
        [admin_review_entry_row(), admin_review_appeals_button_row()],
        [admin_adjust_user_button_row(),admin_create_staff_button_row()],
        [admin_review_reward_button_row(), admin_reward_list_button_row()],
        [admin_mall_entry_row(),lottery_admin_entry_row()],
        [admin_publish_reward_button_row(),],

    ]
    return InlineKeyboardMarkup(keyboard)


def merchant_main_menu():
    keyboard = [


    ]
    return InlineKeyboardMarkup(keyboard)


def user_main_menu():
    keyboard = [
        #提交报告 我的报告
        #兑换名片  兑换历史
        [user_profile_button_row(),user_inheritance_entry_row()],
        [exchange_start_button_row(), exchange_history_button_row()],
        [my_reports_entry_button_row(), user_submit_report_button_row()],
        [user_my_submissions_button_row(),lottery_user_wins_entry_row()],
        [user_mall_entry_row()],
    ]
    return InlineKeyboardMarkup(keyboard)
