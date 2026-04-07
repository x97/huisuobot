import logging
import asyncio
from typing import List, Optional

from django.utils import timezone
from telethon.tl.types import Message

from telethon_account.telethon_manager import default_manager
from ingestion.models import IngestionSource
from telethon.tl.functions.messages import GetHistoryRequest

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

async def safe_get_channel(client, source):
    """
    安全获取频道实体：
    1. 优先用 username
    2. 失败则用 -100 开头的 channel_id
    """
    entity = None

    # ======================
    # 第一步：尝试 username
    # ======================
    try:
        username = source.channel_username
        if username and username.strip():
            if not username.startswith("@"):
                username = f"@{username}"
            entity = await client.get_entity(username)
            print(f"✅ 通过用户名找到频道: {username}")
            return entity
    except Exception as e:
        print(f"⚠️  用户名方式失败: {e}")

    # ======================
    # 第二步：降级用 ID（必须加 -100）
    # ======================
    try:
        channel_id = source.channel_id
        if str(channel_id).startswith("-100"):
            telegram_id = channel_id
        else:
            telegram_id = int(f"-100{channel_id}")  # 关键！

        entity = await client.get_entity(telegram_id)
        print(f"✅ 通过ID找到频道: {telegram_id}")
        return entity
    except Exception as e:
        print(f"❌ ID方式也失败: {e}")

    return entity

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
    last_id = source.last_message_id or 0   # ⭐ 用 0 更安全
    fetch_mode = source.fetch_mode
    delay = get_safe_delay(source)
    page_limit = min(100, limit)
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    logger.info(
        f"📡 开始抓取频道消息: {source.channel_name or source.channel_username} "
        f"(ID={channel_id}) 使用账号 {account.phone_number}，延迟={delay}s"
    )

    messages = []
    count = 0

    # 获取频道实体
    entity  = await safe_get_channel(client, source)
    if not entity:
        return  []

    try:
        offset_id = 0  # ⭐ 从最新消息开始往前抓

        while True:
            # ⭐ forward 模式：抓 last_id 之后的新消息
            if fetch_mode == "forward":
                history = await client(GetHistoryRequest(
                    peer=entity,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=page_limit,
                    max_id=0,
                    min_id=last_id,  # ⭐ 关键：只抓 id > last_id 的消息
                    hash=0
                ))

            # ⭐ backward 模式：补档，从最旧往后抓
            else:
                history = await client(GetHistoryRequest(
                    peer=entity,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=min(100, limit - count),
                    max_id=last_id,  # ⭐ 关键：只抓 id < last_id 的消息
                    min_id=0,
                    hash=0
                ))

            msgs = history.messages
            if not msgs:
                break

            for msg in msgs:
                # 时间过滤
                if msg.date < cutoff:
                    logger.info(f"⏹️ 停止：msg_id={msg.id} 超过 {max_age_days} 天")
                    return messages

                messages.append(msg)
                count += 1

                logger.info(f"📨 进度：{count}/{limit}（msg_id={msg.id}）")

            # ⭐ 下一页：offset_id = 最后一条消息的 id
            offset_id = msgs[-1].id

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
