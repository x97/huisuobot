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
from places.services import find_place_by_name
from mygroups.services import get_mygroups_cache

logger = logging.getLogger(__name__)

PREFIX = "reward_admin"

WAITING_PLACE = 7001
WAITING_NICKNAME = 7002
WAITING_TITLE = 7003
WAITING_DESCRIPTION = 7004
WAITING_REWARD = 7005
WAITING_CONFIRM = 7006
WAITING_CHANNEL = 7007

def admin_start_publish(update: Update, context: CallbackContext):
    """管理员点击发布悬赏入口"""
    if update.callback_query:
        q = update.callback_query
        q.answer()
        # 👉 这里改提示文字，支持全平台
        q.edit_message_text("请输入要悬赏的场所名称：\n输入 0 或 全平台 = 全平台悬赏\n输入 /cancel 取消当前操作")
    else:
        update.message.reply_text("请输入要悬赏的场所名称：\n输入 0 或 全平台 = 全平台悬赏\n输入 /cancel 取消当前操作")

    return WAITING_PLACE


def admin_input_place(update: Update, context: CallbackContext):
    """管理员输入场所名 → 现在支持 全平台（不选场所）"""
    name = update.message.text.strip()

    # ========================
    # ✅ 关键：支持全平台悬赏
    # ========================
    if name.lower() in ["0", "全平台", "全局", "不限场所"]:
        # 不设置场所 = 全平台
        context.user_data["reward_place_id"] = None  # 👈 核心
        update.message.reply_text("已选择：全平台悬赏\n请输入悬赏标题：\n输入 /cancel 取消当前操作")
        return WAITING_TITLE

    # 原来逻辑：查找场所
    place = find_place_by_name(name)
    if not place:
        update.message.reply_text("未找到场所，请重新输入：\n输入 /cancel 取消当前操作")
        return WAITING_PLACE

    context.user_data["reward_place_id"] = place.id

    #update.message.reply_text(f"已选择场所：{place.name}\n请输入要征集的员工昵称：\n输入 /cancel 取消当前操作")
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
    text = update.message.text.strip()
    if not text.isdigit():
        update.message.reply_text("请输入整数金币数量：\n输入 /cancel 取消当前操作")
        return WAITING_REWARD

    reward = int(text)
    context.user_data["reward_coins"] = reward

    # 初始化频道列表
    context.user_data["reward_channels"] = []

    update.message.reply_text(
        "请输入要发送的频道链接（如 https://t.me/xxxx）：\n"
        "可以多次输入多个频道，每次输入一个。\n\n"
        "点击 /done 进入确认步骤。\n"
        "输入 /cancel 取消当前操作"
    )
    return WAITING_CHANNEL


def admin_input_channel(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    # 解析频道链接
    if not text.startswith("https://t.me/"):
        update.message.reply_text("请输入有效的频道链接（必须以 https://t.me/ 开头）")
        return WAITING_CHANNEL

    # 提取频道用户名
    username = text.replace("https://t.me/", "").strip().replace("@", "")
    if not username:
        update.message.reply_text("无法解析频道链接，请重新输入。")
        return WAITING_CHANNEL

    # 尝试获取频道 ID
    try:
        chat = context.bot.get_chat(f"@{username}")
        channel_id = chat.id
    except Exception:
        update.message.reply_text("无法获取频道信息，请确认机器人已加入该频道并具有权限。")
        return WAITING_CHANNEL

    # 校验是否在 allowed_channels
    allowed_channels = get_mygroups_cache()["allowed_channels"]
    if channel_id not in allowed_channels:
        update.message.reply_text("该频道未在系统允许列表中，无法发送。")
        return WAITING_CHANNEL

    # 保存频道
    context.user_data["reward_channels"].append(channel_id)

    update.message.reply_text(
        f"已添加频道：{username}\n"
        f"当前共 {len(context.user_data['reward_channels'])} 个频道。\n\n"
        "继续输入下一个频道，或点击 /done 进入确认步骤。"
    )
    return WAITING_CHANNEL


def show_reward_summary(update: Update, context: CallbackContext):
    # ========== 核心改动：兼容 场所为 None（全平台） ==========
    place_id = context.user_data.get("reward_place_id")  # 用 get 不会报错
    place = None
    place_text = "【全平台】不限场所"  # 默认全平台

    if place_id:
        try:
            place = Place.objects.get(id=place_id)
            place_text = f"📍场所：{place.name}"
        except Place.DoesNotExist:
            place_text = "【全平台】不限场所"

    channels = context.user_data["reward_channels"]

    summary = (
            "请确认发布悬赏：\n\n"
            f"{place_text}\n"  # 👈 这里自动切换 场所 / 全平台
            f"📌标题：{context.user_data['reward_title']}\n"
            f"📄描述：{context.user_data['reward_description']}\n"
            f"💰奖励金币：{context.user_data['reward_coins']}\n\n"
            f"📢发送频道数量：{len(channels)}\n"
            "频道 ID 列表：\n" + "\n".join([str(c) for c in channels]) + "\n\n"
                                                                        "确认发布吗？"
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

    # ========================
    # ✅ 核心改动：兼容场所为空（全平台）
    # ========================
    place_id = context.user_data.get("reward_place_id")
    place = None
    if place_id:
        place = Place.objects.get(id=place_id)

    channels = context.user_data["reward_channels"]

    # 创建悬赏（place 可以为 None）
    campaign = Campaign.objects.create(
        title=context.user_data["reward_title"],
        place=place,  # 这里可以是 None
        description=context.user_data["reward_description"],
        reward_coins=context.user_data["reward_coins"],
        is_active=True,
    )

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=reward_{campaign.id}"

    # ========================
    # ✅ 智能拼接文本：场所存在/不存在 自动显示
    # ========================
    if place:
        place_text = (
            f"💎 会所名称：{place.name}\n"
            f"📌 所在位置：{place.district}\n"
        )
    else:
        place_text = (
            f"💎 会所名称：【全平台不限场所】\n"
            f"📌 所在位置：全平台通用\n"
        )

    text = (
        f"📢【悬赏征集】-- {campaign.title}\n\n"
        f"{place_text}"  # 👈 自动切换
        f"📄 征集详情: {campaign.description}\n\n"
        f"💰 奖励金币：{campaign.reward_coins}\n\n"
        "👇 点击下方按钮私聊机器人提交悬赏信息\n"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 我要提交", url=deep_link)]
    ])

    # 发送到多个频道
    for channel_id in channels:
        try:
            msg = query.bot.send_message(
                chat_id=channel_id,
                text=text,
                reply_markup=keyboard
            )

            CampaignNotification.objects.create(
                campaign=campaign,
                mygroup_id=None,
                notify_channel_id=channel_id,
                message_id=msg.message_id,
            )
        except Exception as e:
            print(f"发送到频道 {channel_id} 失败：{e}")

    query.edit_message_text("✅ 悬赏已发布成功！", reply_markup=append_back_button(None))
    return ConversationHandler.END


def admin_cancel(update: Update, context: CallbackContext):
    """取消发布"""
    q = update.callback_query
    if q:
        q.answer()
        q.edit_message_text("已取消发布。", reply_markup=append_back_button(None))
    else:
        update.message.reply_text("已取消。", reply_markup=append_back_button(None))
    context.user_data.clear()
    return ConversationHandler.END

def admin_finish_channels(update: Update, context: CallbackContext):
    if not context.user_data.get("reward_channels"):
        update.message.reply_text("至少需要输入一个频道链接。")
        return WAITING_CHANNEL

    return show_reward_summary(update, context)

def get_admin_publish_handler():
    # 关键：避免 /cancel 被当成普通文本
    only_text = Filters.text & ~Filters.regex(r"^/cancel") & Filters.chat_type.private

    return ConversationHandler(
        entry_points=[
            CommandHandler("publish_reward", admin_start_publish),
            CallbackQueryHandler(admin_start_publish, pattern=r"^reward_admin:start$"),
        ],

        states={
            WAITING_PLACE: [
                MessageHandler(only_text, admin_input_place),
            ],
            WAITING_TITLE: [
                MessageHandler(only_text, admin_input_title),
            ],
            WAITING_DESCRIPTION: [
                MessageHandler(only_text, admin_input_description),
            ],
            WAITING_REWARD: [
                MessageHandler(only_text, admin_input_reward),
            ],
            WAITING_CHANNEL: [
                # 只接受【非命令】的文本
                MessageHandler(Filters.text & ~Filters.command, admin_input_channel),
                # /done 命令独立处理
                CommandHandler("done", admin_finish_channels),
            ],

            WAITING_CONFIRM: [
                CallbackQueryHandler(admin_confirm_publish, pattern=rf"^{PREFIX}:confirm$"),
                CallbackQueryHandler(admin_cancel, pattern=rf"^{PREFIX}:cancel$"),
            ],
        },

        fallbacks=[
            CommandHandler("cancel", admin_cancel),
        ],

        per_user=True,
        per_chat=True,
        allow_reentry=True,   # ⭐ 必须加
    )


def register_reward_publish_handlers(dispatcher):
    """
    在 bot 启动时注册管理员发布悬赏的 handlers
    """
    dispatcher.add_handler(get_admin_publish_handler())
