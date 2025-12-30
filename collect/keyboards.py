# collect/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from common.keyboards import single_button, button_row
from common.callbacks import make_cb

PREFIX = "exchange"

def exchange_start_button_row(is_single=True):
    """主菜单或其他地方调用，返回一行按钮（InlineKeyboardButton）"""
    if is_single:
        return single_button("💳 兑换名片", PREFIX, "start")
    return button_row(single_button("💳 兑换名片", PREFIX, "start"))

def admin_review_appeals_button_row(is_single=True):
    """
    返回一行按钮，供管理员菜单或主菜单（仅管理员可见）使用。
    callback_data 格式为: admin_appeal:list
    """
    if is_single:
        return single_button("👨‍💻 审核兑换申诉", "admin_appeal", "list")
    return button_row(single_button("👨‍💻 审核兑换申诉", "admin_appeal", "list"))

def exchange_history_button_row(is_single=True):
    """返回一行“兑换历史”按钮，主菜单可并列显示"""
    if is_single:
        return single_button("📜 兑换历史", PREFIX, "history")
    return button_row(single_button("📜 兑换历史", PREFIX, "history"))

def confirm_cancel_row(place_id: int):
    """确认兑换与取消按钮行"""
    confirm_cb = make_cb(PREFIX, "confirm", place_id)
    cancel_cb = make_cb("core", "back_main")
    return [
        InlineKeyboardButton("✅ 确认兑换", callback_data=confirm_cb),
        InlineKeyboardButton("🔙 取消", callback_data=cancel_cb),
    ]


"""悬赏相关"""

REWARD_PREFIX = "reward"

def reward_submit_button(campaign_id: int):
    """悬赏频道中的提交按钮"""
    return [
        InlineKeyboardButton(
            "📝 我要提交",
            callback_data=make_cb(REWARD_PREFIX, "submit", campaign_id)
        )
    ]


# ============================
# 🔥 新增：管理员悬赏相关按钮
# ============================

def admin_review_reward_button_row(is_single=True):
    """
    管理员审核悬赏提交入口
    callback_data: reward_review:list
    """
    if is_single:
        return single_button("👨‍💻 审核悬赏", "reward_review", "list")

    return button_row(
        single_button("👨‍💻 审核悬赏", "reward_review", "list")
    )


def admin_reward_list_button_row(is_single=True):
    """
    管理员查看悬赏活动列表入口
    callback_data: reward_manage:list:1
    """
    if is_single:
        return single_button("🧾 悬赏活动列表", "reward_manage", "list", 1)

    return button_row(
        single_button("🧾 悬赏活动列表", "reward_manage", "list", 1)
    )


def admin_publish_reward_button_row(is_single=True):
    """
    管理员发布悬赏入口
    callback_data: reward_admin:start
    """
    if is_single:
        return single_button("💸 发布悬赏", "reward_admin", "start")
    return button_row(
        single_button("💸 发布悬赏", "reward_admin", "start")
    )

def user_my_submissions_button_row(is_single=True):
    """
    用户查看自己提交记录入口
    callback_data: my_submissions:list:1
    """
    if is_single:
        return single_button("📄 我提交的征集", "my_submissions", "list", 1)

    return button_row(
        single_button("📄 我提交的征集", "my_submissions", "list", 1)
    )

def admin_create_staff_button_row(is_single=True):
    """
    管理员创建技师入口
    callback_data: staff_admin:create
    """
    btn = single_button("👙 创建技师信息", "staff_admin", "create")
    return btn if is_single else button_row(btn)
