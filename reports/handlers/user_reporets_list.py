# reports/handlers/user_reports_list.py

from typing import Tuple

from django.core.paginator import Paginator, EmptyPage
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler

from common.callbacks import make_cb, parse_cb
from reports.models import Report
from tgusers.models import TelegramUser
from common.keyboards import append_back_button

PREFIX = "reports"
MY_REPORTS_ACTION = "my_reports"
CLOSE_ACTION = "close_my_reports"
BACK_ACTION = ("core", "back_main")
PAGE_SIZE_DEFAULT = 5


def build_my_reports_message_and_keyboard(user_id: int,
                                          page_number: int = 1,
                                          page_size: int = PAGE_SIZE_DEFAULT) -> Tuple[str, InlineKeyboardMarkup]:
    """
    返回 (message_text, InlineKeyboardMarkup)
    callback_data 采用命名空间：
      - 查看页码: reports:my_reports:<page>
      - 关闭: reports:close_my_reports
      - 返回主菜单: core:back_main
    所有增加返回主菜单的动作应调用 append_back_button
    """
    try:
        reporter = TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        # 只有提示文本时也返回带返回主菜单的键盘
        empty_markup = append_back_button(None)
        return "你还没有提交过任何报告。", empty_markup

    qs = Report.objects.filter(reporter=reporter).order_by('-created_at')
    paginator = Paginator(qs, page_size)

    # 修正页码边界
    if page_number < 1:
        page_number = 1
    if paginator.num_pages and page_number > paginator.num_pages:
        page_number = paginator.num_pages

    try:
        current_page = paginator.page(page_number)
    except EmptyPage:
        empty_markup = append_back_button(None)
        return "没有找到更多报告。", empty_markup

    # 构建消息文本
    if current_page.object_list.count() == 0:
        message_text = "你还没有提交过任何报告。"
    else:
        message_text = f"<b>📋 我的报告列表 (第 {page_number}/{paginator.num_pages} 页)</b>\n\n"
        for report in current_page.object_list:
            status_emoji = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}.get(report.status, '')
            review_note = report.review_note or "无"
            created_at = report.created_at.strftime('%Y-%m-%d %H:%M') if getattr(report, "created_at", None) else "未知时间"
            message_text += (
                f"<b>报告 #{report.id}</b> {status_emoji}\n"
                f"<b>状态:</b> {report.get_status_display()}\n"
                f"<b>提交时间:</b> {created_at}\n"
                f"<b>内容:</b> {report.content}\n"
                f"<b>审核备注:</b> {review_note}\n"
                "-----------------------------------------\n"
            )

    # 构建分页键盘（使用 make_cb 生成 callback_data）
    buttons = []

    if current_page.has_previous():
        prev_cb = make_cb(PREFIX, MY_REPORTS_ACTION, current_page.previous_page_number())
        buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=prev_cb))

    close_cb = make_cb(PREFIX, CLOSE_ACTION)
    buttons.append(InlineKeyboardButton("✖️ 关闭", callback_data=close_cb))

    if current_page.has_next():
        next_cb = make_cb(PREFIX, MY_REPORTS_ACTION, current_page.next_page_number())
        buttons.append(InlineKeyboardButton("➡️ 下一页", callback_data=next_cb))

    # 先构造当前行，再通过 append_back_button 追加“返回主菜单”
    base_markup = InlineKeyboardMarkup([buttons])
    reply_markup = append_back_button(base_markup)

    return message_text, reply_markup


def handle_my_reports(update: Update, context: CallbackContext) -> None:
    """
    处理 reports:my_reports[:<page>] 的回调，展示用户自己的报告分页列表。
    """
    query = update.callback_query
    query.answer()

    user_id = update.effective_user.id
    callback_data = query.data or ""

    # 解析 callback_data：优先使用 parse_cb（如果是 make_cb 生成的）
    prefix, action, args = parse_cb(callback_data)
    page_number = 1
    if prefix == PREFIX and action == MY_REPORTS_ACTION:
        if args:
            try:
                page_number = int(args[0])
            except (ValueError, TypeError):
                page_number = 1
    else:
        # 兼容旧格式 "my_reports" 或直接触发
        if callback_data == "my_reports":
            page_number = 1
        else:
            # 尝试从下划线格式解析（向后兼容）
            try:
                page_number = int(callback_data.split('_')[-1])
            except Exception:
                page_number = 1

    message_text, reply_markup = build_my_reports_message_and_keyboard(user_id, page_number)

    try:
        query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        # 如果编辑失败（例如消息被删除），发送新消息
        context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup, parse_mode='HTML')


def close_my_reports(update: Update, context: CallbackContext) -> None:
    """处理 reports:close_my_reports 回调，删除报告列表消息。"""
    query = update.callback_query
    query.answer()
    try:
        query.delete_message()
    except Exception:
        pass


def register_reports_list_handlers(dispatcher):
    """
    注册 reports 命名空间下的“我的报告”相关处理器。
    - 分页/入口: reports:my_reports[:<page>]
    - 关闭: reports:close_my_reports
    """
    dispatcher.add_handler(CallbackQueryHandler(handle_my_reports, pattern=rf"^{PREFIX}:{MY_REPORTS_ACTION}"))
    dispatcher.add_handler(CallbackQueryHandler(close_my_reports, pattern=rf"^{PREFIX}:{CLOSE_ACTION}$"))
