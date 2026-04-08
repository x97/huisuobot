from common.message_utils import send_telegram_message_sync, delete_telegram_message_sync
from celery import shared_task
from mygroups.models import MyGroup
from collect.models import CampaignNotification
import requests
from django.conf import settings

# 🔥 全局内存字典：key=频道ID, value=上一条消息ID
_last_campaign_msg = {}


def _build_telegram_post_url(channel_id: int, message_id: int, username: str | None):
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal_id = str(channel_id).replace("-100", "")
    return f"https://t.me/c/{internal_id}/{message_id}"


def generate_campaign_text_for_channel(notify_channel_id: int, username: str = None):
    notifications = CampaignNotification.objects.filter(
        notify_channel_id=notify_channel_id
    ).select_related("campaign")

    valid_campaigns = []
    for n in notifications:
        campaign = n.campaign
        if campaign and campaign.is_active:
            valid_campaigns.append((campaign, n.message_id))

    if not valid_campaigns:
        return None

    lines = []
    for campaign, msg_id in valid_campaigns:
        url = _build_telegram_post_url(notify_channel_id, msg_id, username)
        lines.append(f"💎 [{campaign.title}](sslocal://flow/file_open?url=%7Burl%7D&flow_extra=eyJsaW5rX3R5cGUiOiJjb2RlX2ludGVycHJldGVyIn0=)    💰{campaign.reward_coins}金币")

    text = "💰💰💰 【悬赏汇总】 💰💰💰\n\n"
    text += "\n".join(lines)
    text += "\n\n\n提交悬赏获取💰金币，每100金币可兑换100元出击补贴"
    return text


@shared_task
def broadcast_campaigns_to_all_groups():
    groups = MyGroup.objects.exclude(notify_channel_id__isnull=True)

    for group in groups:
        channel_id = group.notify_channel_id
        username = group.notify_channel_username

        text = generate_campaign_text_for_channel(channel_id, username)
        if not text:
            continue

        try:
            # ========================
            # 1. 内存里有上一条 → 删掉
            # ========================
            last_msg_id = _last_campaign_msg.get(channel_id)
            if last_msg_id:
                delete_telegram_message_sync(channel_id, last_msg_id)

            # ========================
            # 2. 发新消息
            # ========================
            res = send_telegram_message_sync(
                chat_id=channel_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

            # ========================
            # 3. 新消息ID存入内存
            # ========================
            if res and res.get("ok"):
                new_msg_id = res["result"]["message_id"]
                _last_campaign_msg[channel_id] = new_msg_id

        except Exception:
            continue
