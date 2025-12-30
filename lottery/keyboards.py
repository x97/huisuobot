from common.keyboards import single_button, button_row

from lottery.constant import PREFIX_USER, PREFIX_ADMIN


def lottery_admin_entry_row(is_single=True):
    """
    管理员主菜单中的“抽奖管理”入口
    callback_data: lottery_admin:menu
    """
    btn = single_button("🎟️ 抽奖管理", PREFIX_ADMIN, "menu")
    return btn if is_single else button_row(btn)


def lottery_user_wins_entry_row(is_single=True):
    """
    用户主菜单中的“我的中奖记录”入口
    callback_data: lottery_user:wins
    """
    btn = single_button("🏆 我的中奖记录", PREFIX_USER, "wins")
    return btn if is_single else button_row(btn)

