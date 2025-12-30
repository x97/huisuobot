import logging

from telegram.ext import ChatMemberHandler
from telegram.ext import MessageHandler, Filters
from telegram.error import TelegramError

from mygroups.services import get_mygroups_cache
from bot_core.handlers.common import pre_process_user


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_bot_added(update, context):
    """
    当机器人被加入群/频道时触发。
    如果退出了非法群聊/频道 → 返回 True
    否则 → 返回 False
    """
    chat = update.effective_chat
    my_chat_member = update.my_chat_member

    # 不是 chat_member 更新，直接忽略
    if not chat or not my_chat_member:
        return False

    bot_id = context.bot.id

    # 只处理“机器人自己”的状态变化
    if my_chat_member.new_chat_member.user.id != bot_id:
        return False

    chat_id = chat.id
    chat_type = chat.type
    new_status = my_chat_member.new_chat_member.status

    logger.info(f"[guard] Bot status changed in chat {chat_id} ({chat_type}), new_status={new_status}")

    # 只在机器人被加入时处理（member / administrator）
    if new_status not in ("member", "administrator"):
        return False

    # 获取白名单
    cache = get_mygroups_cache()
    allowed_groups = set(cache["allowed_groups"])
    allowed_channels = set(cache["allowed_channels"])

    # 判断是否允许
    is_allowed = (
        (chat_type in ("group", "supergroup") and chat_id in allowed_groups) or
        (chat_type == "channel" and chat_id in allowed_channels)
    )

    if is_allowed:
        logger.info(f"[guard] Allowed chat, staying: {chat_id} ({chat_type})")
        return False

    # ❌ 不允许 → 退出
    logger.warning(f"[guard] Bot joined unauthorized {chat_type}: {chat_id}, leaving...")

    # 尝试发送提示（频道可能失败）
    try:
        context.bot.send_message(
            chat_id=chat_id,
            text="❌ 抱歉，我仅允许在指定群聊/频道中使用，已自动退出～"
        )
    except Exception as e:
        logger.debug(f"[guard] Cannot send message before leaving {chat_id}: {e}")

    # 执行退群
    try:
        context.bot.leave_chat(chat_id)
        logger.info(f"[guard] Successfully left unauthorized {chat_type}: {chat_id}")
    except Exception as e:
        logger.error(f"[guard] Failed to leave {chat_type} {chat_id}: {e}")

    return True

def handle_other_members_added(update, context):
    pre_process_user(update, context)

def handle_new_chat_members(update, context):
    """
    统一处理新成员加入事件的主函数。
    它会调用其他专门的函数来处理不同的情况。
    """
    # 1. 首先处理机器人自身被添加的情况（修复：await 异步函数）
    bot_has_left = handle_bot_added(update, context)

    # 2. 如果机器人没有退出群聊，再处理其他新成员加入的逻辑（修复：await 异步函数）
    if not bot_has_left:
        handle_other_members_added(update, context)

def register_group_guard(dp):
    # 使用 ChatMemberHandler 替代 MessageHandler
    dp.add_handler(MessageHandler(
        Filters.status_update.new_chat_members,
        handle_new_chat_members
    ))
    dp.add_handler(ChatMemberHandler(
        handle_new_chat_members,
        ChatMemberHandler.MY_CHAT_MEMBER
    ))
