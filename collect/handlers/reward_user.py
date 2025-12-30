# collect/handlers/reward_user.py
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from collect.models import Submission
from tgusers.services import update_or_create_user
# 分页按钮
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from common.callbacks import make_cb
from common.keyboards import append_back_button

logger = logging.getLogger(__name__)

PREFIX = "my_submissions"
PAGE_SIZE = 5


def user_list_submissions(update: Update, context: CallbackContext):
    """用户查看自己提交的征集记录"""
    query = update.callback_query
    is_callback = query is not None

    # 封装统一回复函数
    def send(text, markup=None):
        if is_callback:
            query.edit_message_text(text, reply_markup=markup)
        else:
            update.message.reply_text(text, reply_markup=markup)

    # 获取用户
    user = update.effective_user
    tg_user = update_or_create_user(user)

    if not tg_user:
        send("未找到用户信息，请先与 bot 交互。")
        return

    # 分页
    page = 1
    if is_callback:
        page = int(query.data.split(":")[-1])
        query.answer()

    qs = Submission.objects.filter(reporter=tg_user).order_by("-created_at")
    total = qs.count()

    if total == 0:
        send("你还没有提交过任何征集记录。")
        return

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start = (page - 1) * PAGE_SIZE
    items = qs[start:start + PAGE_SIZE]

    # 构建文本
    lines = [f"📄 你的提交记录（第 {page}/{total_pages} 页）\n"]

    status_map = {
        "pending": "⏳ 待审核",
        "approved": "✅ 已通过",
        "rejected": "❌ 已拒绝",
    }

    for sub in items:
        status_text = status_map.get(sub.status, sub.status)

        lines.append(
            f"提交ID: {sub.id}\n"
            f"活动: {sub.campaign.title}\n"
            f"状态: {status_text}\n"
            f"提交时间: {sub.created_at:%Y-%m-%d %H:%M}\n"
            f"技师号码: {sub.nickname}\n"
            f"颜值评价: {sub.attractiveness}\n"
            f"补充信息: {sub.extra_info}\n"
            "------------------------\n"
        )


    buttons = []
    nav = []

    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb("my_submissions", "list", page - 1)))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=make_cb("my_submissions", "list", page + 1)))

    if nav:
        buttons.append(nav)

    reply_markup = InlineKeyboardMarkup(buttons)
    reply_markup = append_back_button(reply_markup)
    send("\n".join(lines), reply_markup)


def register_reward_user_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("my_submissions", user_list_submissions))

    dispatcher.add_handler(CallbackQueryHandler(
        user_list_submissions,
        pattern=r"^my_submissions:list:\d+$"
    ))
