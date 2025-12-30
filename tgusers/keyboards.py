# tgusers/keyboards.py
from common.keyboards import single_button, button_row
from .constant import PREFIX_USER

def user_profile_button_row(is_single=True):
    """
    用户查看个人信息（积分 / 金币 / 签到日期）
    callback_data: user_profile:show
    """
    if is_single:
        return single_button("👤 我的账户信息", PREFIX_USER, "show")

    return button_row(
        single_button("👤 我的账户信息", PREFIX_USER, "show")
    )


def admin_adjust_user_button_row(is_single=True):
    """
    管理员入口：调整用户积分/金币
    callback_data: adjust_user:start
    """
    if is_single:
        return single_button("⭐ 管理积分/金币", "adjust_user", "start")

    return button_row(
        single_button("⭐ 管理积分/金币", "adjust_user", "start")
    )

def user_inheritance_entry_row(is_single=True):
    """
    用户主菜单中的“继承功能”入口
    callback_data: user:show_inheritance_menu
    """
    btn = single_button("🔗 继承功能", PREFIX_USER, "show_inheritance_menu")
    return btn if is_single else [btn]
