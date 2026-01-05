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
    limit: int = 200,
    max_age_days: int = 180
) -> List[Message]:

    channel_id = source.channel_id
    last_id = source.last_message_id or 1
    fetch_mode = source.fetch_mode
    delay = get_safe_delay(source)

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    logger.info(
        f"📡 开始抓取频道消息: {source.channel_name or source.channel_username} "
        f"(ID={channel_id}) 使用账号 {account.phone_number}，延迟={delay}s"
    )

    messages = []
    count = 0

    try:
        if fetch_mode == "forward":
            iterator = client.iter_messages(
                entity=channel_id,
                min_id=last_id,
                limit=limit,
                reverse=False  # ⭐ forward 必须是 False
            )
        else:
            iterator = client.iter_messages(
                entity=channel_id,
                max_id=last_id,
                reverse=True,
                limit=limit
            )

        async for msg in iterator:

            # 时间过滤
            if msg.date < cutoff:
                logger.info(f"⏹️ 停止：msg_id={msg.id} 超过 {max_age_days} 天")
                break

            count += 1
            logger.info(f"📨 进度：{count}/{limit}（msg_id={msg.id}）")

            messages.append(msg)

            await asyncio.sleep(delay)

        logger.info(f"📥 抓取完成，共 {len(messages)} 条消息")
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
