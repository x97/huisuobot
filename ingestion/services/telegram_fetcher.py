import logging
import asyncio
from typing import List, Optional

from django.utils import timezone
from telethon.tl.types import Message

from telethon_account.telethon_manager import default_manager
from ingestion.models import IngestionSource

logger = logging.getLogger(__name__)


# ============================
# 🔧 获取安全延迟（默认 4 秒）
# ============================
def get_safe_delay(source: IngestionSource) -> float:
    """
    从 extra_config 读取 delay，如果没有则默认 4 秒。
    """
    try:
        return float(source.extra_config.get("delay", 4))
    except Exception:
        return 4


# ============================
# 🔥 1. 抓取频道消息（增量）
# ============================
@default_manager.with_account_switching()
async def fetch_channel_messages(
    *,
    client,
    account,
    source: IngestionSource,
    limit: int = 200
) -> List[Message]:

    channel_id = source.channel_id
    last_id = source.last_message_id or 0
    fetch_mode = source.fetch_mode  # forward / backward
    delay = get_safe_delay(source)

    logger.info(
        f"📡 开始抓取频道消息: {source.channel_name or source.channel_username} "
        f"(ID={channel_id}) 使用账号 {account.phone_number}，延迟={delay}s"
    )

    messages = []

    try:
        # forward 模式：抓取 last_id 之后的新消息
        if fetch_mode == "forward":
            async for msg in client.iter_messages(
                entity=channel_id,
                min_id=last_id,
                limit=limit
            ):
                messages.append(msg)
                await asyncio.sleep(delay)  # ⭐ 安全延迟

        # backward 模式：从最旧往后抓（适合补档）
        else:
            async for msg in client.iter_messages(
                entity=channel_id,
                max_id=last_id,
                reverse=True,
                limit=limit
            ):
                messages.append(msg)
                await asyncio.sleep(delay)  # ⭐ 安全延迟

        logger.info(f"📥 抓取到 {len(messages)} 条消息")
        return messages

    except Exception as e:
        logger.error(f"❌ 抓取频道消息失败: {e}", exc_info=True)
        return []


# ============================
# 🔥 2. 抓取频道用户（tguser）
# ============================
@default_manager.with_account_switching()
async def fetch_channel_users(
    *,
    client,
    account,
    source: IngestionSource,
    limit: int = 500
):
    channel_id = source.channel_id
    delay = get_safe_delay(source)

    logger.info(
        f"👥 开始抓取频道用户: {source.channel_name or source.channel_username} "
        f"(ID={channel_id}) 使用账号 {account.phone_number}，延迟={delay}s"
    )

    try:
        participants = await client.get_participants(channel_id, limit=limit)
        await asyncio.sleep(delay)  # ⭐ 安全延迟

        logger.info(f"📥 抓取到 {len(participants)} 个用户")
        return participants

    except Exception as e:
        logger.error(f"❌ 抓取频道用户失败: {e}", exc_info=True)
        return []


# ============================
# 🔥 3. 抓取单条消息（用于补档）
# ============================
@default_manager.with_account_switching()
async def fetch_single_message(
    *,
    client,
    account,
    source: IngestionSource,
    message_id: int
) -> Optional[Message]:

    delay = get_safe_delay(source)

    try:
        msg = await client.get_messages(source.channel_id, ids=message_id)
        await asyncio.sleep(delay)  # ⭐ 安全延迟
        return msg
    except Exception as e:
        logger.error(f"❌ 获取消息 {message_id} 失败: {e}")
        return None


# ============================
# 🔥 4. 更新抓取进度
# ============================
def update_source_progress(source: IngestionSource, messages: List[Message]):
    if not messages:
        return

    new_last_id = max(msg.id for msg in messages)

    source.last_message_id = new_last_id
    source.last_fetched_at = timezone.now()
    source.save(update_fields=["last_message_id", "last_fetched_at"])

    logger.info(f"📌 更新抓取进度: last_message_id = {new_last_id}")
