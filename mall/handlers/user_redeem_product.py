import logging
from django.utils import timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
from common.callbacks import make_cb
from common.keyboards import append_back_button
from mall.models import MallProduct, RedemptionRecord
from tgusers.services import update_or_create_user

logger = logging.getLogger(__name__)

PREFIX = "mall_user"

WAITING_CONFIRM = 8301


def user_start_redeem(update: Update, context: CallbackContext):
    """用户点击兑换按钮入口"""
    q = update.callback_query
    q.answer()
    product_id = int(q.data.split(":")[-1])

    try:
        product = MallProduct.objects.get(id=product_id, is_active=True, stock__gt=0)
    except MallProduct.DoesNotExist:
        q.edit_message_text("❌ 商品不存在或已下架。", reply_markup=append_back_button(None))
        return ConversationHandler.END

    user = update_or_create_user(update.effective_user)
    # 校验余额
    if product.points_needed > 0:
        if user.points < product.points_needed:
            q.edit_message_text(f"❌ 积分不足，需要 {product.points_needed} 积分，你当前 {user.points} 积分。")
            return ConversationHandler.END
        cost_text = f"{product.points_needed} 积分"
    else:
        if user.coins < product.coins_needed:
            q.edit_message_text(f"❌ 金币不足，需要 {product.coins_needed} 金币，你当前 {user.coins} 金币。")
            return ConversationHandler.END
        cost_text = f"{product.coins_needed} 金币"

    context.user_data["redeem_product_id"] = product.id

    summary = (
        f"⚠️ 确认兑换以下商品？\n\n"
        f"📦 名称：{product.name}\n"
        f"📝 描述：{product.description[:60]}...\n"
        f"💰 消耗：{cost_text}\n"
        f"📊 库存：{product.stock}\n\n"
        "✅确认兑换吗？"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认兑换", callback_data=make_cb(PREFIX, "confirm")),
            InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel")),
        ]
    ])

    q.edit_message_text(summary, reply_markup=keyboard)
    return WAITING_CONFIRM


def user_confirm_redeem(update: Update, context: CallbackContext):
    """用户确认兑换商品"""
    q = update.callback_query
    q.answer()
    product_id = context.user_data.get("redeem_product_id")
    user = update_or_create_user(update.effective_user)

    try:
        product = MallProduct.objects.get(id=product_id, is_active=True, stock__gt=0)
    except MallProduct.DoesNotExist:
        q.edit_message_text("❌ 商品不存在或已下架。", reply_markup=append_back_button(None))
        return ConversationHandler.END

    # 扣减余额
    if product.points_needed > 0:
        user.points -= product.points_needed
    else:
        user.coins -= product.coins_needed
    user.save()

    # 扣减库存
    product.stock -= 1
    product.save()

    # 创建兑换记录
    redemption = RedemptionRecord.objects.create(user=user, product=product)

    q.edit_message_text(
        f"🎉 兑换成功！\n\n"
        f"📦 商品：{product.name}\n"
        f"🎟️ 核销码：`{redemption.verification_code}`\n"
        f"📝 状态：待核销\n"
        f"💎 剩余积分：{user.points}   🪙 剩余金币：{user.coins}",
        reply_markup=append_back_button(None),
        parse_mode="Markdown"
    )

    return ConversationHandler.END


def user_cancel_redeem(update: Update, context: CallbackContext):
    """用户取消兑换"""
    q = update.callback_query
    q.answer()
    q.edit_message_text("❌ 已取消兑换操作。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_user_redeem_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_start_redeem, pattern=r"^mall_user:redeem:\d+$"),
        ],
        states={
            WAITING_CONFIRM: [
                CallbackQueryHandler(user_confirm_redeem, pattern=rf"^{PREFIX}:confirm$"),
                CallbackQueryHandler(user_cancel_redeem, pattern=rf"^{PREFIX}:cancel$"),
            ],
        },
        fallbacks=[],
    )


def register_user_redeem_handlers(dispatcher):
    dispatcher.add_handler(get_user_redeem_handler())
