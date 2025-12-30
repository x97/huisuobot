# mall/handlers/admin_add_product.py

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
)
from common.callbacks import make_cb
from common.keyboards import append_back_button
from mall.models import MallProduct

logger = logging.getLogger(__name__)

PREFIX = "mall_admin"

WAITING_NAME = 8001
WAITING_DESC = 8002
WAITING_TYPE = 8003
WAITING_POINTS = 8004
WAITING_COINS = 8005
WAITING_STOCK = 8006
WAITING_CONFIRM = 8007


def admin_start_add(update: Update, context: CallbackContext):
    """管理员点击添加商品入口"""
    if update.callback_query:
        q = update.callback_query
        q.answer()
        q.edit_message_text("请输入商品名称：\n输入 /cancel 取消当前操作")
    else:
        update.message.reply_text("请输入商品名称：\n输入 /cancel 取消当前操作")
    print("准备进入 WAITING_NAME")
    return WAITING_NAME


def admin_input_name(update: Update, context: CallbackContext):
    """管理员输入商品名称"""
    print("？？？？？")
    name = update.message.text.strip()
    print("收到输入商品", name)
    if not name:
        update.message.reply_text("商品名称不能为空，请重新输入：\n输入 /cancel 取消当前操作")
        return WAITING_NAME

    context.user_data["product_name"] = name
    update.message.reply_text("请输入商品描述：\n输入 /cancel 取消当前操作")
    return WAITING_DESC


def admin_input_desc(update: Update, context: CallbackContext):
    """管理员输入商品描述"""
    print("商品描述 status")
    desc = update.message.text.strip()
    context.user_data["product_desc"] = desc

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏆 积分兑换", callback_data=make_cb(PREFIX, "use_points")),
            InlineKeyboardButton("💰 金币兑换", callback_data=make_cb(PREFIX, "use_coins")),
        ]
    ])
    update.message.reply_text("请选择商品兑换方式：", reply_markup=keyboard)
    return WAITING_TYPE


def admin_choose_type(update: Update, context: CallbackContext):
    """管理员选择兑换方式"""
    q = update.callback_query
    q.answer()
    if q.data.endswith("use_points"):
        context.user_data["use_points"] = True
        q.edit_message_text("请输入所需积分：\n输入 /cancel 取消当前操作")
        return WAITING_POINTS
    else:
        context.user_data["use_points"] = False
        q.edit_message_text("请输入所需金币：\n输入 /cancel 取消当前操作")
        return WAITING_COINS


def admin_input_points(update: Update, context: CallbackContext):
    """管理员输入所需积分"""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        update.message.reply_text("请输入正整数积分：\n输入 /cancel 取消当前操作")
        return WAITING_POINTS

    context.user_data["points_needed"] = int(text)
    update.message.reply_text("请输入库存数量：\n输入 /cancel 取消当前操作")
    return WAITING_STOCK


def admin_input_coins(update: Update, context: CallbackContext):
    """管理员输入所需金币"""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        update.message.reply_text("请输入正整数金币：\n输入 /cancel 取消当前操作")
        return WAITING_COINS

    context.user_data["coins_needed"] = int(text)
    update.message.reply_text("请输入库存数量：\n输入 /cancel 取消当前操作")
    return WAITING_STOCK


def admin_input_stock(update: Update, context: CallbackContext):
    """管理员输入库存数量"""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 0:
        update.message.reply_text("请输入非负整数库存：\n输入 /cancel 取消当前操作")
        return WAITING_STOCK

    context.user_data["stock"] = int(text)

    # 展示确认信息
    name = context.user_data["product_name"]
    desc = context.user_data["product_desc"]
    if context.user_data.get("use_points"):
        cost = f"{context.user_data['points_needed']} 积分"
    else:
        cost = f"{context.user_data['coins_needed']} 金币"
    stock = context.user_data["stock"]

    summary = (
        "请确认商品信息：\n\n"
        f"📦 名称：{name}\n"
        f"📝 描述：{desc}\n"
        f"💰 消耗：{cost}\n"
        f"📊 库存：{stock}\n\n"
        "✅确认添加吗？"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认添加", callback_data=make_cb(PREFIX, "confirm")),
            InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel")),
        ]
    ])

    update.message.reply_text(summary, reply_markup=keyboard)
    return WAITING_CONFIRM


def admin_confirm_add(update: Update, context: CallbackContext):
    """确认添加商品"""
    q = update.callback_query
    q.answer()

    try:
        MallProduct.objects.create(
            name=context.user_data["product_name"],
            description=context.user_data["product_desc"],
            points_needed=context.user_data.get("points_needed", 0),
            coins_needed=context.user_data.get("coins_needed", 0),
            stock=context.user_data["stock"],
            is_active=True,
        )
        q.edit_message_text("商品已成功添加！", reply_markup=append_back_button(None))
    except Exception as e:
        logger.error(f"添加商品失败: {e}")
        q.edit_message_text("❌ 添加商品失败！", reply_markup=append_back_button(None))

    return ConversationHandler.END


def admin_cancel(update: Update, context: CallbackContext):
    """取消添加商品"""
    q = update.callback_query
    if q:
        q.answer()
        q.edit_message_text("已取消添加商品。", reply_markup=append_back_button(None))
    else:
        update.message.reply_text("已取消。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_admin_add_product_handler():
    only_text = Filters.text & ~Filters.command & Filters.chat_type.private

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_start_add, pattern=r"^mall_admin:add$"),
        ],
        states={
            WAITING_NAME: [MessageHandler(only_text, admin_input_name)],
            WAITING_DESC: [MessageHandler(only_text, admin_input_desc)],
            WAITING_TYPE: [
                CallbackQueryHandler(admin_choose_type, pattern=rf"^{PREFIX}:(use_points|use_coins)$")
            ],
            WAITING_POINTS: [MessageHandler(only_text, admin_input_points)],
            WAITING_COINS: [MessageHandler(only_text, admin_input_coins)],
            WAITING_STOCK: [MessageHandler(only_text, admin_input_stock)],
            WAITING_CONFIRM: [
                CallbackQueryHandler(admin_confirm_add, pattern=rf"^{PREFIX}:confirm$"),
                CallbackQueryHandler(admin_cancel, pattern=rf"^{PREFIX}:cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )



def register_admin_add_product_handlers(dispatcher):
    """在 bot 启动时注册管理员添加商品的 handlers"""
    dispatcher.add_handler(get_admin_add_product_handler())
