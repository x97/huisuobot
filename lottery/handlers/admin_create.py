# lottery/handlers/admin_create.py

import datetime
from django.utils import timezone
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler,
    CommandHandler, Filters, CallbackContext
)

from tgusers.services import update_or_create_user
from common.keyboards import append_back_button
from lottery.models import Lottery, Prize
from lottery.services import send_lottery_to_group
from mygroups.services import load_mygroups_cache
from lottery.tasks import add_lottery_draw_job


# 状态
TITLE, CHAT_LINK, END_TIME, REQUIRED_POINTS, PRIZE_NAME, PRIZE_QUANTITY, DESCRIPTION, CONFIRM = range(40, 48)


# -------------------------
# 工具：管理员判断
# -------------------------
def admin_check(update, context):
    tguser = update_or_create_user(update.effective_user)
    if not tguser.is_admin:
        update.effective_message.reply_text(
            "❌ 你不是管理员，无权使用此功能",
            reply_markup=append_back_button(None)
        )
        return False
    return True


# -------------------------
# 入口：开始创建抽奖
# -------------------------
def start_create_lottery(update: Update, context: CallbackContext):
    if not admin_check(update, context):
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["lottery"] = {}
    context.user_data["prizes"] = []

    update.effective_message.reply_text(
        "📢 开始创建抽奖\n请输入抽奖标题：",
        reply_markup=ReplyKeyboardRemove()
    )
    return TITLE


# -------------------------
# 步骤 1：标题
# -------------------------
def handle_title(update, context):
    title = update.message.text.strip()
    if not title:
        update.message.reply_text("标题不能为空，请重新输入：")
        return TITLE

    context.user_data["lottery"]["title"] = title
    update.message.reply_text("请输入群组链接（https://t.me/xxx）：")
    return CHAT_LINK


# -------------------------
# 工具：解析群组链接
# -------------------------
def get_chat_id_from_link(context, chat_link):
    import re
    pattern = r'(https?://t\.me/)(joinchat/)?([a-zA-Z0-9_-]+)'
    match = re.search(pattern, chat_link)
    if not match:
        return None

    invite_path = match.group(3)
    try:
        chat = context.bot.get_chat(f"@{invite_path}")
        return chat.id
    except:
        return None


# -------------------------
# 步骤 2：群组链接
# -------------------------
def handle_chat_link(update, context):
    chat_link = update.message.text.strip()
    if not chat_link.startswith("https://t.me/"):
        update.message.reply_text("链接格式错误，请重新输入：")
        return CHAT_LINK

    all_groups = load_mygroups_cache().get("allowed_groups", [])
    chat_id = get_chat_id_from_link(context, chat_link)
    if not chat_id or chat_id not in all_groups:
        update.message.reply_text("❌ 群组无效，请重新输入：")
        return CHAT_LINK

    context.user_data["lottery"]["chat_id"] = chat_id
    update.message.reply_text("请输入开奖时间（YYYY-MM-DD HH:MM）：")
    return END_TIME


# -------------------------
# 步骤 3：开奖时间
# -------------------------
def handle_end_time(update, context):
    text = update.message.text.strip()
    try:
        end_time = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
        if end_time < datetime.datetime.now():
            raise ValueError
    except:
        update.message.reply_text("时间格式错误，请重新输入：")
        return END_TIME

    context.user_data["lottery"]["end_time"] = end_time
    update.message.reply_text("请输入参与积分（正整数）：")
    return REQUIRED_POINTS


# -------------------------
# 步骤 4：积分
# -------------------------
def handle_required_points(update, context):
    try:
        points = int(update.message.text.strip())
        if points <= 0:
            raise ValueError
    except:
        update.message.reply_text("积分必须为正整数，请重新输入：")
        return REQUIRED_POINTS

    context.user_data["lottery"]["required_points"] = points
    update.message.reply_text("请输入第一个奖品名称：")
    return PRIZE_NAME


# -------------------------
# 步骤 5：奖品名称
# -------------------------
def handle_prize_name(update, context):
    name = update.message.text.strip()
    if not name:
        update.message.reply_text("奖品名称不能为空，请重新输入：")
        return PRIZE_NAME

    context.user_data["temp_prize_name"] = name
    update.message.reply_text("请输入奖品数量（正整数）：")
    return PRIZE_QUANTITY


# -------------------------
# 步骤 6：奖品数量
# -------------------------
def handle_prize_quantity(update, context):
    try:
        qty = int(update.message.text.strip())
        if qty <= 0:
            raise ValueError
    except:
        update.message.reply_text("数量必须为正整数，请重新输入：")
        return PRIZE_QUANTITY

    name = context.user_data.pop("temp_prize_name")
    context.user_data["prizes"].append({"name": name, "quantity": qty})

    keyboard = [[InlineKeyboardButton("🔚 结束添加奖品", callback_data="lottery:admin:end_prizes")]]
    update.message.reply_text(
        f"已添加奖品：{name}（{qty}份）\n继续输入下一个奖品名称，或点击按钮结束。",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PRIZE_NAME


# -------------------------
# 结束添加奖品
# -------------------------
def handle_end_prizes(update, context):
    query = update.callback_query
    query.answer()

    if len(context.user_data["prizes"]) == 0:
        query.edit_message_text("至少需要一个奖品，请输入奖品名称：")
        return PRIZE_NAME

    query.edit_message_text("请输入兑奖说明：")
    return DESCRIPTION


# -------------------------
# 步骤 7：兑奖说明
# -------------------------
def handle_description(update, context):
    desc = update.message.text.strip()
    if not desc:
        update.message.reply_text("兑奖说明不能为空，请重新输入：")
        return DESCRIPTION

    context.user_data["lottery"]["description"] = desc

    l = context.user_data["lottery"]
    prizes = context.user_data["prizes"]

    text = f"🎉 抽奖预览\n标题：{l['title']}\n积分：{l['required_points']}\n开奖：{l['end_time']}\n\n奖品：\n"
    for p in prizes:
        text += f"- {p['name']} × {p['quantity']}\n"

    keyboard = [
        [InlineKeyboardButton("✅ 确认发布", callback_data="lottery:admin:publish")],
        [InlineKeyboardButton("❌ 取消", callback_data="lottery:admin:cancel")]
    ]

    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM


# -------------------------
# 发布抽奖
# -------------------------
def confirm_publish_lottery(update, context):
    query = update.callback_query
    query.answer()

    data = context.user_data["lottery"]
    prizes = context.user_data["prizes"]

    lottery = Lottery.objects.create(
        title=data["title"],
        description=data["description"],
        required_points=data["required_points"],
        end_time=timezone.make_aware(data["end_time"]),
        group_id=data["chat_id"],
        is_active=True,
    )

    for p in prizes:
        Prize.objects.create(lottery=lottery, name=p["name"], quantity=p["quantity"])

    send_lottery_to_group(context, lottery)
    add_lottery_draw_job(lottery)

    query.edit_message_text(f"🎉 抽奖《{lottery.title}》已发布！")
    context.user_data.clear()
    return ConversationHandler.END


# -------------------------
# 取消创建
# -------------------------
def cancel_create_lottery(update, context):
    update.message.reply_text("已取消创建。", reply_markup=append_back_button(None))
    context.user_data.clear()
    return ConversationHandler.END


# -------------------------
# 注册
# -------------------------
def register_admin_create_handlers(dp):
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_create_lottery, pattern=r"^lottery:admin:create$"),
            CommandHandler("create_lottery", start_create_lottery),
        ],
        states={
            TITLE: [MessageHandler(Filters.text & ~Filters.command, handle_title)],
            CHAT_LINK: [MessageHandler(Filters.text & ~Filters.command, handle_chat_link)],
            END_TIME: [MessageHandler(Filters.text & ~Filters.command, handle_end_time)],
            REQUIRED_POINTS: [MessageHandler(Filters.text & ~Filters.command, handle_required_points)],
            PRIZE_NAME: [
                MessageHandler(Filters.text & ~Filters.command, handle_prize_name),
                CallbackQueryHandler(handle_end_prizes, pattern=r"^lottery:admin:end_prizes$")
            ],
            PRIZE_QUANTITY: [MessageHandler(Filters.text & ~Filters.command, handle_prize_quantity)],
            DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, handle_description)],
            CONFIRM: [CallbackQueryHandler(confirm_publish_lottery, pattern=r"^lottery:admin:publish$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_create_lottery)],
        per_user=True,
        per_chat=True,
    )

    dp.add_handler(conv)
