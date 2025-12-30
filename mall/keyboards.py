from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from common.callbacks import make_cb
from common.keyboards import single_button, button_row

PREFIX_ADMIN = "mall_admin"
PREFIX_USER = "mall_user"

def admin_mall_manager_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 添加商品", callback_data=make_cb(PREFIX_ADMIN, "add"))],
        [InlineKeyboardButton("📋 管理商品", callback_data=make_cb(PREFIX_ADMIN, "manage"))],
        [InlineKeyboardButton("✅ 核销商品", callback_data=make_cb(PREFIX_ADMIN, "verify"))],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data=make_cb("core", "back_main"))],
    ])

def user_mall_manager_main_menu(user):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 商品列表", callback_data=make_cb(PREFIX_USER, "list"))],
        [InlineKeyboardButton("📜 我的兑换记录", callback_data=make_cb(PREFIX_USER, "history"))],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data=make_cb("core", "back_main"))],
    ])


def admin_mall_entry_row(is_single=True):
    """
    管理员主菜单中的“积分商城管理”入口
    callback_data: mall_admin:menu
    """
    btn = single_button("🛒️ 积分商城管理", PREFIX_ADMIN, "menu")
    return btn if is_single else button_row(btn)


def user_mall_entry_row(is_single=True):
    """
    用户主菜单中的“积分商城”入口
    callback_data: mall_user:menu
    """
    btn = single_button("🛍️ 积分商城", PREFIX_USER, "menu")
    return btn if is_single else button_row(btn)
