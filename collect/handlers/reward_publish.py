# collect/handlers/reward_publish.py

import logging
from django.utils import timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
)
from common.callbacks import make_cb
from common.keyboards import append_back_button
from collect.models import Campaign, CampaignNotification
from places.models import Place
from mygroups.models import MyGroup

logger = logging.getLogger(__name__)

PREFIX = "reward_admin"

WAITING_PLACE = 7001
WAITING_NICKNAME = 7002
WAITING_TITLE = 7003
WAITING_DESCRIPTION = 7004
WAITING_REWARD = 7005
WAITING_CONFIRM = 7006


def admin_start_publish(update: Update, context: CallbackContext):
    """管理员点击发布悬赏入口"""
    if update.callback_query:
        q = update.callback_query
        q.answer()
        q.edit_message_text("请输入要悬赏的场所名称：\n输入 /cancel 取消当前操作")
    else:
        update.message.reply_text("请输入要悬赏的场所名称：\n输入 /cancel 取消当前操作")

    return WAITING_PLACE



def admin_input_place(update: Update, context: CallbackContext):
    """管理员输入场所名"""
    name = update.message.text.strip()
    qs = Place.objects.filter(name__icontains=name)
    if not qs.exists():
        update.message.reply_text("未找到场所，请重新输入：\n输入 /cancel 取消当前操作")
        return WAITING_PLACE

    place = qs.first()
    context.user_data["reward_place_id"] = place.id

    update.message.reply_text(f"已选择场所：{place.name}\n请输入要征集的员工昵称：\n输入 /cancel 取消当前操作")
    return WAITING_NICKNAME


def admin_input_nickname(update: Update, context: CallbackContext):
    """管理员输入员工昵称"""
    nickname = update.message.text.strip()
    context.user_data["reward_nickname"] = nickname

    update.message.reply_text("请输入悬赏标题：\n输入 /cancel 取消当前操作")
    return WAITING_TITLE


def admin_input_title(update: Update, context: CallbackContext):
    """管理员输入悬赏标题"""
    title = update.message.text.strip()
    context.user_data["reward_title"] = title

    update.message.reply_text("请输入悬赏描述（可多行）：\n输入 /cancel 取消当前操作")
    return WAITING_DESCRIPTION


def admin_input_description(update: Update, context: CallbackContext):
    """管理员输入悬赏描述"""
    description = update.message.text.strip()
    context.user_data["reward_description"] = description

    update.message.reply_text("请输入奖励金币数量（整数）：\n输入 /cancel 取消当前操作")
    return WAITING_REWARD


def admin_input_reward(update: Update, context: CallbackContext):
    """管理员输入奖励金币"""
    text = update.message.text.strip()
    if not text.isdigit():
        update.message.reply_text("请输入整数金币数量：\n输入 /cancel 取消当前操作")
        return WAITING_REWARD

    reward = int(text)
    context.user_data["reward_coins"] = reward

    # 展示确认信息
    place = Place.objects.get(id=context.user_data["reward_place_id"])

    summary = (
        "请确认发布悬赏：\n\n"
        f"📍场所：{place.name}\n"
        f"👩征集员工：{context.user_data['reward_nickname']}\n"
        f"📌标题：{context.user_data['reward_title']}\n"
        f"📄描述：{context.user_data['reward_description']}\n"
        f"💰奖励金币：{reward}\n\n"
        "✅确认发布吗？"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认发布", callback_data=make_cb(PREFIX, "confirm")),
            InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel")),
        ]
    ])

    update.message.reply_text(summary, reply_markup=keyboard)
    return WAITING_CONFIRM


def admin_confirm_publish(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    place = Place.objects.get(id=context.user_data["reward_place_id"])

    campaign = Campaign.objects.create(
        title=context.user_data["reward_title"],
        place=place,
        description=context.user_data["reward_description"],
        reward_coins=context.user_data["reward_coins"],
        is_active=True,
    )

    group = MyGroup.objects.first()
    if not group or not group.notify_channel_id:
        query.edit_message_text("未配置通知频道，无法发布悬赏。")
        return ConversationHandler.END

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=reward_{campaign.id}"

    text = (
        f"📢【悬赏征集】-- {campaign.title}\n\n"
        f"💎 会所名称：{place.name}\n"
        f"📌 所在位置：{place.district}\n"
        f"👩 技师号码：{context.user_data['reward_nickname']}\n\n"
        f"📄 征集详情: {campaign.description}\n\n"
        f"💰 奖励金币：{campaign.reward_coins}\n\n"
        "👇 点击下方按钮私聊机器人提交悬赏信息\n"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 我要提交", url=deep_link)]
    ])

    msg = query.bot.send_message(
        chat_id=group.notify_channel_id,
        text=text,
        reply_markup=keyboard
    )

    CampaignNotification.objects.create(
        campaign=campaign,
        mygroup_id=group.id,
        notify_channel_id=group.notify_channel_id,
        message_id=msg.message_id,
    )

    query.edit_message_text("悬赏已发布成功！", reply_markup=append_back_button(None))
    return ConversationHandler.END


def admin_cancel(update: Update, context: CallbackContext):
    """取消发布"""
    q = update.callback_query
    if q:
        q.answer()
        q.edit_message_text("已取消发布。", reply_markup=append_back_button(None))
    else:
        update.message.reply_text("已取消。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_admin_publish_handler():
    only_text = Filters.text & ~Filters.command & Filters.chat_type.private

    return ConversationHandler(
        entry_points=[
            CommandHandler("publish_reward", admin_start_publish),
            CallbackQueryHandler(admin_start_publish, pattern=r"^reward_admin:start$"),
        ],

        states={
            WAITING_PLACE: [MessageHandler(only_text, admin_input_place)],
            WAITING_NICKNAME: [MessageHandler(only_text, admin_input_nickname)],
            WAITING_TITLE: [MessageHandler(only_text, admin_input_title)],
            WAITING_DESCRIPTION: [MessageHandler(only_text, admin_input_description)],
            WAITING_REWARD: [MessageHandler(only_text, admin_input_reward)],
            WAITING_CONFIRM: [
                CallbackQueryHandler(admin_confirm_publish, pattern=rf"^{PREFIX}:confirm$"),
                CallbackQueryHandler(admin_cancel, pattern=rf"^{PREFIX}:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
    )

def register_reward_publish_handlers(dispatcher):
    """
    在 bot 启动时注册管理员发布悬赏的 handlers
    """
    dispatcher.add_handler(get_admin_publish_handler())
