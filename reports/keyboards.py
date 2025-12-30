# reports/keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common.callbacks import make_cb
from common.keyboards import  append_back_button, row

PREFIX = "reports"
BACK_PREFIX = ("core", "back_main")


from common.keyboards import single_button, button_row

def user_submit_report_button_row(is_single=True):
    # 返回一行按钮，主菜单可以把它和其他行并列
    if is_single:
        return  single_button("📝 提交报告", PREFIX, "start_report")
    return button_row(single_button("📝 提交报告", PREFIX, "start_report"))

def my_reports_entry_button_row(is_single=True):
    # 传入页码 1
    if is_single:
        return single_button("📋 我的报告", PREFIX, "my_reports", 1)

    return button_row(single_button("📋 我的报告", PREFIX, "my_reports", 1))


def admin_review_entry_row(is_single=True):
    """
    管理员主菜单中的“审核报告”入口（触发显示第1页/第1条）
    返回一行 InlineKeyboardButton（主菜单合并时使用）
    callback_data: reports:review_reports:1
    """
    if is_single:
        return single_button("🧾 审核报告", PREFIX, "review_reports", 1)
    return button_row(single_button("🧾 审核报告", PREFIX, "review_reports", 1))

def admin_report_action_rows(report_id: int):
    """
    审核消息内使用的操作行（通过/驳回/查看/返回）
    返回 List[List[InlineKeyboardButton]]
    """
    row1 = button_row(
        single_button("✅ 通过", PREFIX, "approve_report", report_id),
        single_button("❌ 驳回", PREFIX, "reject_report", report_id),
    )
    row2 = button_row(
        single_button("🔎 查看详情", PREFIX, "view", report_id),
        single_button("🔙 返回", "core", "back_main")
    )
    return [row1, row2]

def confirm_cancel_buttons():
    # 用于确认页面的两个按钮（确认/取消）
    kb = [
        [ single_button("✅ 确认提交", PREFIX, "confirm_report"),
          single_button("❌ 取消", PREFIX, "cancel_report") ]
    ]
    return InlineKeyboardMarkup(kb)


def my_reports_page_buttons(page: int, has_prev: bool, has_next: bool):
    """
    返回 InlineKeyboardMarkup，用于“我的报告”分页底部按钮。
    - page: 当前页（用于生成下一页/上一页的 target）
    - has_prev / has_next: 是否显示上一页/下一页
    callback_data:
      - reports:my_reports:<page>
      - reports:close_my_reports
      - core:back_main
    """
    buttons = []

    if has_prev:
        prev_cb = make_cb(PREFIX, "my_reports", page - 1)
        buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=prev_cb))

    # 关闭
    close_cb = make_cb(PREFIX, "close_my_reports")
    buttons.append(InlineKeyboardButton("✖️ 关闭", callback_data=close_cb))

    # 返回主菜单（core:back_main）
    back_cb = make_cb(*BACK_PREFIX)
    buttons.append(InlineKeyboardButton("🏠 返回主菜单", callback_data=back_cb))

    if has_next:
        next_cb = make_cb(PREFIX, "my_reports", page + 1)
        buttons.append(InlineKeyboardButton("➡️ 下一页", callback_data=next_cb))

    return InlineKeyboardMarkup([buttons])


def report_detail_buttons(report_id: int, include_admin_actions: bool = False):
    """
    报告详情页的按钮：
    - 普通用户：关闭/返回
    - 管理员（include_admin_actions=True）：通过/驳回/返回
    callback_data:
      - reports:view:<id>
      - reports:approve:<id>
      - reports:reject:<id>
      - core:back_main
    """
    kb = []
    if include_admin_actions:
        kb.append([
            single_button("✅ 通过", PREFIX, "approve", report_id),
            single_button("❌ 驳回", PREFIX, "reject", report_id),
        ])
    kb.append([single_button("🔎 查看详情", PREFIX, "view", report_id)])
    # 最后一行返回主菜单
    return append_back_button(kb)

def my_reports_page_buttons(page: int, has_prev: bool, has_next: bool):
    buttons = []
    if has_prev:
        buttons.append(single_button("⬅️ 上一页", PREFIX, "my_reports", page - 1))
    buttons.append(single_button("✖️ 关闭", PREFIX, "close_my_reports"))
    buttons.append(InlineKeyboardButton("🏠 返回主菜单", callback_data=make_cb(*BACK_PREFIX)))
    if has_next:
        buttons.append(single_button("➡️ 下一页", PREFIX, "my_reports", page + 1))
    return InlineKeyboardMarkup([buttons])
