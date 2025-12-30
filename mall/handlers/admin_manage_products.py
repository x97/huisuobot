import logging
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
from mall.models import MallProduct

logger = logging.getLogger(__name__)

PREFIX = "mall_admin"

WAITING_MANAGE = 8101
WAITING_CONFIRM = 8102
PAGE_SIZE = 5


def admin_start_manage(update: Update, context: CallbackContext, page: int = 1):
    """管理员点击商品管理入口"""
    q = update.callback_query
    q.answer()

    products = MallProduct.objects.all().order_by("-id")
    total = products.count()
    if total == 0:
        q.edit_message_text("暂无商品，请先添加商品。", reply_markup=append_back_button(None))
        return ConversationHandler.END

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    current_products = products[start_idx:end_idx]

    text = f"📋 商品管理（第{page}/{total_pages}页）：\n请选择要操作的商品：\n"
    keyboard = []
    for p in current_products:
        status = "上架中" if p.is_active else "已下架"
        action = "deactivate" if p.is_active else "activate"
        text += f"{p.id}. {p.name} - {status}\n"
        keyboard.append([
            InlineKeyboardButton(
                f"{'下架' if p.is_active else '上架'} {p.name}",
                callback_data=make_cb(PREFIX, action, p.id)
            )
        ])

    # 分页按钮
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb(PREFIX, "manage", page - 1)))
    if page < total_pages:
        row.append(InlineKeyboardButton("➡️ 下一页", callback_data=make_cb(PREFIX, "manage", page + 1)))
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 返回商城管理", callback_data=make_cb(PREFIX, "menu"))])

    q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_MANAGE


def admin_choose_toggle(update: Update, context: CallbackContext):
    """管理员选择上下架商品"""
    q = update.callback_query
    q.answer()
    parts = q.data.split(":")
    action, product_id = parts[1], int(parts[2])
    context.user_data["manage_action"] = action
    context.user_data["manage_product_id"] = product_id

    product = MallProduct.objects.get(id=product_id)
    summary = f"⚠️ 确认要{'下架' if action=='deactivate' else '上架'}商品《{product.name}》吗？"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认", callback_data=make_cb(PREFIX, "confirm_manage")),
            InlineKeyboardButton("❌ 取消", callback_data=make_cb(PREFIX, "cancel_manage")),
        ]
    ])
    q.edit_message_text(summary, reply_markup=keyboard)
    return WAITING_CONFIRM


def admin_confirm_manage(update: Update, context: CallbackContext):
    """确认上下架商品"""
    q = update.callback_query
    q.answer()
    product_id = context.user_data.get("manage_product_id")
    action = context.user_data.get("manage_action")

    try:
        product = MallProduct.objects.get(id=product_id)
        product.is_active = (action == "activate")
        product.save()
        q.edit_message_text(f"✅ 商品《{product.name}》已{'上架' if product.is_active else '下架'}成功！", reply_markup=append_back_button(None))
    except Exception as e:
        logger.error(f"商品上下架失败: {e}")
        q.edit_message_text("❌ 操作失败！", reply_markup=append_back_button(None))

    return ConversationHandler.END


def admin_cancel_manage(update: Update, context: CallbackContext):
    """取消商品管理操作"""
    q = update.callback_query
    q.answer()
    q.edit_message_text("已取消操作。", reply_markup=append_back_button(None))
    return ConversationHandler.END


def get_admin_manage_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_start_manage, pattern=r"^mall_admin:manage$"),
        ],
        states={
            WAITING_MANAGE: [
                CallbackQueryHandler(
                    lambda u, c: admin_start_manage(u, c, int(u.callback_query.data.split(":")[-1])),
                    pattern=rf"^{PREFIX}:manage:\d+$"
                ),
                CallbackQueryHandler(admin_choose_toggle, pattern=rf"^{PREFIX}:(activate|deactivate):\d+$"),
            ],
            WAITING_CONFIRM: [
                CallbackQueryHandler(admin_confirm_manage, pattern=rf"^{PREFIX}:confirm_manage$"),
                CallbackQueryHandler(admin_cancel_manage, pattern=rf"^{PREFIX}:cancel_manage$"),
            ],
        },
        fallbacks=[],
    )


def register_admin_manage_handlers(dispatcher):
    dispatcher.add_handler(get_admin_manage_handler())
