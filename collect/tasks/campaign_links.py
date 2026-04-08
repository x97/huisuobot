from common.message_utils import send_telegram_message_sync  # 👈 导入同步函数
from celery import shared_task
from mygroups.models import MyGroup
from collect.models import CampaignNotification

# 你已有的工具函数
def _build_telegram_post_url(channel_id: int, message_id: int, username: str | None):
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal_id = str(channel_id).replace("-100", "")
    return f"https://t.me/c/{internal_id}/{message_id}"


# ===================== 公共函数：根据频道ID生成文案 =====================
def generate_campaign_text_for_channel(notify_channel_id: int, username: str = None):
    """
    公共核心函数
    根据 notify_channel_id 生成属于这个频道的悬赏列表文案
    完全按 CampaignNotification 筛选
    """
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
        url = _build_telegram_post_url(
            channel_id=notify_channel_id,
            message_id=msg_id,
            username=username
        )
        lines.append(f"💎 [{campaign.title}]({url})    💰{campaign.reward_coins}金币")

    text = "💰💰💰 【悬赏汇总】 💰💰💰\n\n"
    text += "\n".join(lines)
    text += "\n\n\n提交悬赏获取💰金币，每100金币可兑换100元出击补贴"
    return text


# ===================== Celery 定时任务 → 改为同步发送 =====================
@shared_task
def broadcast_campaigns_to_all_groups():
    """
    每小时给所有群广播属于自己的悬赏列表
    """
    groups = MyGroup.objects.exclude(notify_channel_id__isnull=True)

    for group in groups:
        channel_id = group.notify_channel_id
        username = group.notify_channel_username

        text = generate_campaign_text_for_channel(channel_id, username)
        if not text:
            continue

        # ✅ 改为 同步发送（一定能发出去）
        try:
            send_telegram_message_sync(  # 👈 直接用同步函数
                chat_id=channel_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception:
            continue
