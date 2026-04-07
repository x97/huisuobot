# collect/handlers/reward_manage.py
# 管理员查看已发布悬赏 → 分页 → 结束悬赏 → 删除频道消息
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from django.utils import timezone
from datetime import timedelta
from collect.models import Campaign, CampaignNotification
from common.callbacks import make_cb
from common.keyboards import append_back_button
from collect.models import Submission

logger = logging.getLogger(__name__)

PREFIX = "reward_manage"
PAGE_SIZE = 5


def admin_list_campaigns(update: Update, context: CallbackContext):
    """分页显示最近三个月未结束的悬赏（含提交统计）"""
    page = 1
    if update.callback_query:
        page = int(update.callback_query.data.split(":")[-1])
        update.callback_query.answer()

    # 只显示最近三个月 + 未结束
    three_months_ago = timezone.now() - timedelta(days=180)
    qs = Campaign.objects.filter(
        is_active=True,
        created_at__gte=three_months_ago
    ).order_by("-created_at")

    total = qs.count()
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1

    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    items = qs[start:start + PAGE_SIZE]

    lines = [f"📋 悬赏活动列表（第 {page}/{total_pages} 页）\n"]
    buttons = []

    for c in items:
        total_sub = c.submission_set.count()
        pending = c.submission_set.filter(status="pending").count()
        approved = c.submission_set.filter(status="approved").count()
        rejected = c.submission_set.filter(status="rejected").count()

        lines.append(
            f"ID:{c.id} | {c.title} | 进行中\n"
            f"提交：{total_sub}（待审 {pending} / 通过 {approved} / 拒绝 {rejected}）\n"
        )

        buttons.append([
            InlineKeyboardButton("🔚 结束活动", callback_data=make_cb(PREFIX, "end", c.id))
        ])

    # 分页按钮
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb(PREFIX, "list", page - 1)))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=make_cb(PREFIX, "list", page + 1)))
    if nav:
        buttons.append(nav)

    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        update.callback_query.edit_message_text("\n".join(lines), reply_markup=markup)
    else:
        update.message.reply_text("\n".join(lines), reply_markup=markup)

def admin_end_campaign(update: Update, context: CallbackContext):
    """结束悬赏活动并更新频道消息按钮"""
    query = update.callback_query
    query.answer()

    campaign_id = int(query.data.split(":")[-1])
    campaign = Campaign.objects.get(id=campaign_id)

    # 标记活动已结束
    campaign.is_active = False
    campaign.save(update_fields=["is_active"])

    # 更新频道消息按钮
    for n in campaign.notifications.all():
        try:
            # 构造“已结束”按钮
            total = Submission.objects.filter(campaign=campaign).count()

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"❌ 已结束 ({total}人已提交)",
                        callback_data="noop"
                    )
                ]
            ])

            # 更新频道消息（不删除）
            query.bot.edit_message_reply_markup(
                chat_id=n.notify_channel_id,
                message_id=n.message_id,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"更新频道消息失败: {e}")

    # 管理员反馈界面

    reply_markup = append_back_button(None)

    query.edit_message_text(
        "悬赏活动已结束，频道消息已更新为【已结束】。",
        reply_markup=reply_markup
    )



def register_reward_manage_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("reward_list", admin_list_campaigns))

    # 分页按钮
    dispatcher.add_handler(CallbackQueryHandler(
        admin_list_campaigns,
        pattern=r"^reward_manage:list:\d+$"
    ))

    # 结束活动
    dispatcher.add_handler(CallbackQueryHandler(
        admin_end_campaign,
        pattern=r"^reward_manage:end:\d+$"
    ))
