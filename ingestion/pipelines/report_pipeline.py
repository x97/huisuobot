# ingestion/pipeline.py

import asyncio
from django.utils import timezone
from django.conf import settings
from tgusers.models import TelegramUser
from reports.models import Report
from ingestion.services import fetch_channel_messages, parse_report
from ingestion.models import IngestionSource


async def run_ingestion_pipeline():
    """
    主入口：遍历所有 IngestionSource，抓取消息 → 清洗 → 保存到 Report
    """
    sources = IngestionSource.objects.filter(is_active=True)

    for source in sources:
        print(f"📡 开始抓取频道：{source.channel_name or source.channel_username}")

        messages = await fetch_channel_messages(
            channel_id=source.channel_id,
            last_message_id=source.last_message_id
        )

        if not messages:
            print("⚠️ 无新消息")
            continue

        max_message_id = source.last_message_id or 0

        for msg in messages:
            # 更新最大 message_id
            if msg.id > max_message_id:
                max_message_id = msg.id

            # 解析消息
            parsed = parse_report(msg)
            if not parsed:
                continue

            # 保存到 Report
            save_report_from_parsed(parsed)

        # 更新抓取进度
        source.last_message_id = max_message_id
        source.last_fetched_at = timezone.now()
        source.save()

        print(f"✅ 完成：{source.channel_name}（最新 message_id={max_message_id}）")


def save_report_from_parsed(parsed):
    """
    parsed = {
        "content": "...",
        "image_path": "...",   # 可选
    }
    """

    # 1. 使用系统默认用户作为 reporter
    default_user_id = getattr(settings, "REPORT_DEFAULT_USER_ID", None)
    if not default_user_id:
        raise ValueError("请在 settings 中配置 REPORT_DEFAULT_USER_ID")

    reporter = TelegramUser.objects.get(user_id=default_user_id)

    # 2. 创建 Report（只保存 content）
    report = Report.objects.create(
        reporter=reporter,
        content=parsed["content"],
    )

    print(f"📝 已保存 Report #{report.id}")
