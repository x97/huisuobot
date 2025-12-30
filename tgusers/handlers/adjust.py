from telegram.ext import (
    CallbackContext,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    Filters,
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from tgusers.models import TelegramUser
from common.callbacks import make_cb
from common.keyboards import append_back_button

PREFIX = "adjust_user"

WAITING_ACTION = 9001
WAITING_TARGET = 9002
WAITING_VALUE = 9003

def send(update: Update, text: str, markup=None):
    if update.callback_query:
        update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


def adjust_start(update: Update, context: CallbackContext):
    """入口：管理员输入 /adjust_points 或点击按钮"""
    user = update.effective_user
    tg_user = TelegramUser.objects.filter(user_id=user.id).first()
    if not tg_user or not (tg_user.is_admin or tg_user.is_super_admin):
        send(update, "❌ 你没有权限执行此操作。")
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ 增加积分", callback_data=make_cb(PREFIX, "add_points")),
            InlineKeyboardButton("➖ 扣除积分", callback_data=make_cb(PREFIX, "sub_points")),
        ],
        [
            InlineKeyboardButton("💰 增加金币", callback_data=make_cb(PREFIX, "add_coins")),
            InlineKeyboardButton("🪙 扣除金币", callback_data=make_cb(PREFIX, "sub_coins")),
        ],
    ])
    markup = append_back_button(keyboard)
    send(update, "请选择操作类型：", markup=markup)
    return WAITING_ACTION



def adjust_choose_target(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    parts = q.data.split(":")
    # parts = ["adjust_user", "add_points"]
    if len(parts) >= 2:
        action = parts[1]
        context.user_data["adjust_action"] = action
    else:
        # fallback，避免报错
        context.user_data["adjust_action"] = None

    q.edit_message_text(
        "请发送目标用户：\n\n"
        "• @username\n"
        "• user_id\n"
        "• 直接转发该用户的消息\n\n"
        "输入 /cancel 可随时取消操作"
    )
    return WAITING_TARGET



def parse_target_user(update: Update, context: CallbackContext):
    """解析目标用户"""
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        update.message.reply_text("已取消当前操作。")
        return ConversationHandler.END

    # 转发消息
    if update.message.forward_from:
        fwd = update.message.forward_from
        tg_target, _ = TelegramUser.objects.get_or_create(
            user_id=fwd.id,
            defaults=dict(
                username=fwd.username,
                first_name=fwd.first_name,
                last_name=fwd.last_name,
                is_bot=fwd.is_bot,
                has_interacted=True,
            )
        )
        context.user_data["adjust_target"] = tg_target
        update.message.reply_text("目标用户已识别，请输入数值：")
        return WAITING_VALUE

    # @username
    if text.startswith("@"):
        username = text[1:]
        tg_target = TelegramUser.objects.filter(username__iexact=username).first()
        if tg_target:
            context.user_data["adjust_target"] = tg_target
            update.message.reply_text(f"目标用户：@{username}\n请输入数值：")
            return WAITING_VALUE
        update.message.reply_text("❌ 未找到该用户名，请重新输入或 /cancel 取消。")
        return WAITING_TARGET

    # user_id
    if text.isdigit():
        uid = int(text)
        tg_target = TelegramUser.objects.filter(user_id=uid).first()
        if tg_target:
            context.user_data["adjust_target"] = tg_target
            update.message.reply_text(f"目标用户：{uid}\n请输入数值：")
            return WAITING_VALUE
        update.message.reply_text("❌ 未找到该 user_id，请重新输入或 /cancel 取消。")
        return WAITING_TARGET

    update.message.reply_text("❌ 无法识别用户，请重新输入或 /cancel 取消。")
    return WAITING_TARGET


def adjust_apply(update: Update, context: CallbackContext):
    """输入数值 → 执行操作"""
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        update.message.reply_text("已取消当前操作。")
        return ConversationHandler.END

    if not text.lstrip("-").isdigit():
        update.message.reply_text("❌ 请输入有效数字。")
        return WAITING_VALUE

    value = int(text)
    action = context.user_data.get("adjust_action")
    tg_target = context.user_data.get("adjust_target")

    if not action or not tg_target:
        update.message.reply_text("❌ 状态丢失，请重新开始。")
        return ConversationHandler.END

    if action == "add_points":
        tg_target.points += value
        op_text = f"已为用户增加 {value} 积分。"
    elif action == "sub_points":
        tg_target.points -= value
        op_text = f"已为用户扣除 {value} 积分。"
    elif action == "add_coins":
        tg_target.coins += value
        op_text = f"已为用户增加 {value} 金币。"
    elif action == "sub_coins":
        tg_target.coins -= value
        op_text = f"已为用户扣除 {value} 金币。"

    tg_target.save()
    context.user_data.pop("adjust_action", None)
    context.user_data.pop("adjust_target", None)

    update.message.reply_text(
        f"🎉 操作成功！\n\n"
        f"👤 用户：{tg_target.username or tg_target.user_id}\n"
        f"{op_text}\n"
        f"当前积分：{tg_target.points}\n"
        f"当前金币：{tg_target.coins}"
    )
    return ConversationHandler.END


def cancel_adjust(update: Update, context: CallbackContext):
    update.message.reply_text("已取消当前操作。")
    return ConversationHandler.END


def get_adjust_handler():
    only_text = Filters.text & ~Filters.command & Filters.chat_type.private
    return ConversationHandler(
        entry_points=[
            CommandHandler("adjust_points", adjust_start),
            CallbackQueryHandler(adjust_start, pattern=r"^adjust_user:start$"),
        ],
        states={
            WAITING_ACTION: [
                CallbackQueryHandler(adjust_choose_target, pattern=rf"^{PREFIX}:(add_points|sub_points|add_coins|sub_coins)$")
            ],
            WAITING_TARGET: [MessageHandler(only_text, parse_target_user)],
            WAITING_VALUE: [MessageHandler(only_text, adjust_apply)],
        },
        fallbacks=[CommandHandler("cancel", cancel_adjust)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )


def register_adjust_handlers(dispatcher):
    dispatcher.add_handler(get_adjust_handler())
