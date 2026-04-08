from telegram.ext import MessageHandler, Filters
from tgusers.services import update_or_create_user, process_sign_in, process_message_points
from botconfig.services import get_bot_config
from collect.models import CampaignNotification


def sign_in_handler(update, context):
    """签到处理"""
    if not update.effective_user or not update.message:
        return

    text = update.message.text.strip()
    config = get_bot_config()
    keywords = [kw.strip() for kw in config.sign_in_keywords.split(",")]

    if text not in keywords:
        return  # ⭐ 不是签到关键词，跳过

    tg_user = update.effective_user
    user = update_or_create_user(tg_user)

    ok, msg = process_sign_in(user)
    update.message.reply_text(msg)


def user_message_handler(update, context):
    """积分处理"""
    if not update or not update.message:
        return

    message = update.message
    chat = update.effective_chat
    user = update.effective_user

    if not message:
        return

    # 自动同步的频道帖子一定有 forward_from_chat
    if hasattr(message, "forward_from_chat"):
        return

    if chat.type not in ("group", "supergroup"):
        return

    if user.is_bot:
        return

    text = message.text or ""
    if not text:
        return

    # ⭐ 排除查询语句
    if text.startswith("查") or "#" in text:
        return

    # ⭐ 排除签到语句
    config = get_bot_config()
    keywords = [kw.strip() for kw in config.sign_in_keywords.split(",")]
    if text in keywords:
        return

    # ⭐ 正常积分处理
    tg_user = update_or_create_user(user)
    points = process_message_points(tg_user, chat.id, text)

    if points > 0:
        message.reply_text(f"✨ 获得 {points} 积分 ✨")


def discussion_forward_handler(update, context):
    msg = update.message
    if not msg:
        return

    # 自动同步的频道帖子一定有 forward_from_chat
    if not msg.forward_from_chat:
        return

    if msg.forward_from_chat.type != "channel":
        return

    channel_id = msg.forward_from_chat.id
    channel_msg_id = msg.forward_from_message_id

    discuss_msg_id = msg.message_id

    CampaignNotification.objects.filter(
        notify_channel_id=channel_id,
        channel_message_id=channel_msg_id,
        discuss_message_id__isnull=True
    ).update(
        discuss_message_id=discuss_msg_id
    )

    print(f"[DISCUSS] 已更新 discuss_message_id={discuss_msg_id}")


def register_user_activity(dp):
    """注册签到 + 积分 + 讨论组同步"""

    # 1. 签到（优先级高）
    dp.add_handler(
        MessageHandler(
            Filters.text & (~Filters.command) & Filters.chat_type.groups,
            sign_in_handler
        ),
        group=0
    )

    # 2. 积分（优先级低）
    dp.add_handler(
        MessageHandler(
            Filters.text & (~Filters.command) & Filters.chat_type.groups,
            user_message_handler
        ),
        group=1
    )

    dp.add_handler(
        MessageHandler(
            Filters.chat_type.groups,
            discussion_forward_handler
        ),
        group=2
    )

