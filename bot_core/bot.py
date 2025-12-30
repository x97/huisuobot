import logging

from django.conf import settings

from telegram import Update, Bot
from telegram.ext import CallbackContext, MessageHandler, Filters
from telegram.ext import Updater
from telegram.utils.request import Request
from mygroups.services import get_mygroups_cache

from bot_core.handlers import register_handlers

logger = logging.getLogger(__name__)

def leave_unallowed_groups_on_startup():
    """机器人启动时，检查并退出所有非允许群/频道"""
    try:
        proxy_settings = getattr(settings, 'PROXY_SETTINGS', {}) or {}
        request = Request(**proxy_settings)
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, request=request)

        cache = get_mygroups_cache()
        allowed_groups = set(cache["allowed_groups"])
        allowed_channels = set(cache["allowed_channels"])

        logger.info(f"[startup-check] Allowed groups: {allowed_groups}")
        logger.info(f"[startup-check] Allowed channels: {allowed_channels}")

        updates = bot.get_updates()
        joined_chats = set()

        for update in updates:
            chat = None

            if update.message:
                chat = update.message.chat

                if update.message.new_chat_members:
                    for member in update.message.new_chat_members:
                        if member.is_bot:
                            joined_chats.add((chat.id, chat.type))

            if update.channel_post:
                chat = update.channel_post.chat

            if update.my_chat_member:
                chat = update.my_chat_member.chat

            if update.chat_member:
                chat = update.chat_member.chat

            # ❗ 过滤掉私聊
            if chat and chat.type != "private":
                joined_chats.add((chat.id, chat.type))

        logger.info(f"[startup-check] Found {len(joined_chats)} chats from updates")

        for chat_id, chat_type in joined_chats:

            if chat_id not in allowed_groups and chat_id not in allowed_channels:
                logger.warning(f"[startup-check] Unauthorized chat {chat_type}: {chat_id}, leaving...")

                try:
                    bot.send_message(
                        chat_id=chat_id,
                        text="❌ 抱歉，我仅允许在指定群聊/频道中使用，已自动退出～"
                    )
                except Exception as e:
                    logger.debug(f"[startup-check] Cannot send message to {chat_id}: {e}")

                try:
                    bot.leave_chat(chat_id)
                    logger.info(f"[startup-check] Successfully left chat: {chat_id}")
                except Exception as e:
                    logger.error(f"[startup-check] Failed to leave chat {chat_id}: {e}")

            else:
                logger.info(f"[startup-check] Allowed chat: {chat_id}, staying.")

    except Exception as e:
        logger.error(f"[startup-check] Failed: {str(e)}")


def create_bot(token: str):
    """Create and configure the Telegram bot."""
    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher

    # 注册所有 handlers
    register_handlers(dp)

    return updater
