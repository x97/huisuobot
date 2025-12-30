# collect/handlers/exchange_place.py
import logging
from django.db import transaction
from django.utils import timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
)

from places.models import Place, Marketing
from collect.models import ExchangeRecord
from tgusers.models import TelegramUser
from common.callbacks import make_cb
from common.keyboards import append_back_button
from common.utils import mask_phone, mask_wechat  # 请确保实现了这两个函数
from collect.keyboards import exchange_start_button_row, exchange_history_button_row, confirm_cancel_row
from .status_code import EXCHANGE_WAITING_FOR_PLACE, EXCHANGE_WAITING_CONFIRM
from common.keyboards import append_back_button
logger = logging.getLogger(__name__)
PREFIX = "exchange"


def exchange_start(update: Update, context: CallbackContext):
    """入口：列出所有可兑换场所并提示输入场所名"""
    query = update.callback_query
    if query:
        query.answer()
    places = Place.objects.filter(exchange_points__gt=0).order_by("city", "district", "name")
    if not places.exists():
        text = "⚠️当前没有可兑换的场所。"
        if query:
            query.edit_message_text(text=text, reply_markup=append_back_button(None))
        else:
            update.message.reply_text(text, reply_markup=append_back_button(None))
        return ConversationHandler.END

    lines = ["可兑换场所（输入名称或关键字进行搜索）：\n"]
    for p in places:
        lines.append(f"💎 {p.name} -- {p.district or '未知区域'} |  {p.exchange_points} 分")
    text = "\n".join(lines)
    text += ("\n\n\n⌨️请输入你要兑换的场所名（支持部分匹配）"
             "\n输入 /cancel 取消当前操作 ")

    if query:
        try:
            query.edit_message_text(text)
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text=text)
    else:
        update.message.reply_text(text)

    # 保存候选 id 以便后续校验（可选）
    context.user_data['exchange_candidate_ids'] = list(places.values_list("id", flat=True))
    return EXCHANGE_WAITING_FOR_PLACE

def exchange_input_place(update: Update, context: CallbackContext):
    """用户输入场所名，展示前 3 个打码的营销信息并提供确认按钮"""
    user_text = update.message.text.strip()
    qs = Place.objects.filter(exchange_points__gt=0, name__icontains=user_text)
    if not qs.exists():
        update.message.reply_text("未找到匹配的可兑换场所，请检查名称后重试，或输入更短的关键字。")
        return EXCHANGE_WAITING_FOR_PLACE

    place = qs.first()
    marketings = list(place.marketings.all())
    if not marketings:
        update.message.reply_text("该场所暂无营销信息，无法兑换。")
        return ConversationHandler.END

    # 展示前 3 个营销信息（若不足则全部展示）
    show_count = min(3, len(marketings))
    lines = [
        f"💎 场所: {place.name}",
        f"📌 区域: {place.district or '未知'}",
        f"🔔 所需积分: {place.exchange_points}",
        f"✍️ 场所简介: {place.description}\n"
        "---------------------------------",
        "以下为该场所的营销信息（已打码）：",
    ]
    # 保存展示的 marketing id 列表，默认选择第一个作为兑换目标
    shown_marketing_ids = []
    for idx in range(show_count):
        m = marketings[idx]
        shown_marketing_ids.append(m.id)
        masked_phone = mask_phone(m.phone)
        masked_wechat = mask_wechat(m.wechat)
        lines.append(f"{idx + 1}. 营销名: {m.name}")
        lines.append(f"☎️电话: {masked_phone}   🛰️微信: {masked_wechat}")
        lines.append("")

    lines.append("✅确认兑换将扣除相应积分并显示真实联系方式。是否确认？")
    text = "\n".join(lines)

    # 保存上下文以便确认时使用：默认使用第一个展示的 marketing
    context.user_data['exchange_place_id'] = place.id
    context.user_data['exchange_marketing_id'] = shown_marketing_ids[0]
    context.user_data['exchange_shown_marketing_ids'] = shown_marketing_ids

    keyboard = InlineKeyboardMarkup([confirm_cancel_row(place.id)])
    update.message.reply_text(text, reply_markup=keyboard)
    return EXCHANGE_WAITING_CONFIRM



def exchange_confirm(update: Update, context: CallbackContext):
    """用户点击确认兑换，扣积分并展示前 3 个真实联系方式并保存兑换记录"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    query.answer()

    # 从上下文中读取 place_id 和 marketing 列表
    place_id = context.user_data.get("exchange_place_id")
    shown_marketing_ids = context.user_data.get("exchange_shown_marketing_ids", [])
    if not place_id or not shown_marketing_ids:
        query.edit_message_text("会话已过期，请重新输入场所名称。")
        return ConversationHandler.END

    place = Place.objects.filter(id=place_id, exchange_points__gt=0).first()
    if not place:
        query.edit_message_text("该场所不可兑换或不存在。")
        return ConversationHandler.END

    tg_user = TelegramUser.objects.filter(user_id=query.from_user.id).first()
    if not tg_user:
        query.answer("未找到用户信息，请先与 bot 交互一次。", show_alert=True)
        return ConversationHandler.END

    if tg_user.points < place.exchange_points:
        query.edit_message_text(
            f"你的积分不足，当前积分 {tg_user.points}，需要 {place.exchange_points}。"
        )
        return ConversationHandler.END

    # 扣积分并保存记录（事务）
    with transaction.atomic():
        tg_user.points -= place.exchange_points
        tg_user.save(update_fields=["points"])

        # 默认使用第一个 marketing 作为记录的 marketing
        first_marketing = Marketing.objects.filter(id=shown_marketing_ids[0]).first()

        record = ExchangeRecord.objects.create(
            user=tg_user,
            place=place,
            marketing=first_marketing,
            points=place.exchange_points,
        )

    # 展示前 3 个真实联系方式
    marketings = list(Marketing.objects.filter(id__in=shown_marketing_ids))
    show_count = min(3, len(marketings))

    lines = [
        f"🎉 兑换成功！已扣除 {place.exchange_points} 分。\n",
        f"💎 场所: {place.name}",
        f"📌 区域: {place.district or '未知'}",
        f"✍️ 场所简介: {place.description}",
        "---------------------------------",
        "以下为该场所的真实联系方式：",
    ]

    for idx in range(show_count):
        m = marketings[idx]
        real_phone = m.phone or "无"
        real_wechat = m.wechat or "无"
        lines.append(f"{idx + 1}. 营销名: {m.name}")
        lines.append(f"☎️电话: {real_phone}   🛰️微信: {real_wechat}")
        lines.append("")

    lines.append("兑换记录已保存，可在兑换历史中查看或申诉。")

    text = "\n".join(lines)

    try:
        query.edit_message_text(text, reply_markup=append_back_button(None))
    except Exception:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=append_back_button(None)
        )

    # 清理上下文
    context.user_data.pop("exchange_place_id", None)
    context.user_data.pop("exchange_marketing_id", None)
    context.user_data.pop("exchange_shown_marketing_ids", None)

    return ConversationHandler.END



def cancel_exchange(update: Update, context: CallbackContext):
    """通用取消回退到主菜单（fallback）"""
    query = update.callback_query
    if query:
        query.answer()
        try:
            reply_markup = append_back_button(None)
            query.edit_message_text("已取消。", reply_markup=reply_markup)
        except Exception:
            context.bot.send_message(chat_id=query.message.chat_id, text="已取消。", reply_markup=reply_markup)
    else:
        reply_markup = append_back_button(None)
        update.message.reply_text("已取消。", reply_markup=reply_markup)
    return ConversationHandler.END


def get_exchange_conversation_handler() -> ConversationHandler:
    """构造 ConversationHandler 并返回，供注册使用"""
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(exchange_start, pattern=rf"^{PREFIX}:start$"),
            CommandHandler("exchange", exchange_start),
            CommandHandler("cancel", cancel_exchange),

        ],
        states={
            EXCHANGE_WAITING_FOR_PLACE: [
                MessageHandler(Filters.text & ~Filters.command, exchange_input_place),
                CommandHandler("cancel", cancel_exchange),
            ],
            EXCHANGE_WAITING_CONFIRM: [
                CallbackQueryHandler(exchange_confirm, pattern=rf"^{PREFIX}:confirm:\d+$"),
                CommandHandler("cancel", cancel_exchange),

            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_exchange, pattern=rf"^core:back_main$"),
            CommandHandler("cancel", cancel_exchange),

        ],
        per_user=True,
    )
    return conv


def register_exchange_handlers(dispatcher):
    """在主注册点调用此函数注册所有与兑换相关的 handlers"""
    dispatcher.add_handler(get_exchange_conversation_handler())
