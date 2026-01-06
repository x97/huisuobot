from django.core.paginator import Paginator
from mygroups.models import MyGroup
from collect.models import Campaign, CampaignNotification


def list_campaign_links_task(page: int, page_size: int, **kwargs):
    """
    返回分页后的悬赏列表，每行一个 Markdown 链接：
    [标题](url)

    :return: text(str), total_pages(int)
    """

    # 1) 查询所有有效悬赏
    qs = Campaign.objects.filter(is_active=True).order_by("-created_at")

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    lines = []

    for campaign in page_obj.object_list:
        # 2) 找到通知记录
        notify = campaign.notifications.first()
        if not notify:
            continue

        channel_id = notify.notify_channel_id
        message_id = notify.message_id

        # 3) 找到 MyGroup（为了拿 username）
        mygroup = MyGroup.objects.filter(notify_channel_id=channel_id).first()

        # 4) 生成跳转链接
        url = _build_telegram_post_url(
            channel_id=channel_id,
            message_id=message_id,
            username=mygroup.notify_channel_username if mygroup else None
        )

        # 5) 拼接 Markdown 链接
        lines.append(f"[{campaign.title}]({url})")

    text = "\n".join(lines) if lines else "暂无悬赏信息"

    return text, paginator.num_pages


def _build_telegram_post_url(channel_id: int, message_id: int, username: str | None):
    """
    根据频道是否公开自动生成跳转链接。
    公开频道： https://t.me/<username>/<message_id>
    私密频道： https://t.me/c/<internal_id>/<message_id>
    """

    if username:  # 公开频道
        return f"https://t.me/{username}/{message_id}"

    # 私密频道：chat_id = -1001234567890 → internal_id = 1234567890
    internal_id = str(channel_id).replace("-100", "")
    return f"https://t.me/c/{internal_id}/{message_id}"
