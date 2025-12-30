# tgusers/handlers/inheritance_handler.py

import logging
import uuid
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
    CommandHandler,
)
from django.db import transaction
from tgusers.models import TelegramUser
from tgusers.keyboards import single_button
from common.keyboards import append_back_button
from common.utils import end_all_conversations  # 确保你有这个工具函数
from tgusers.constant import PREFIX_USER
# 定义对话状态

logger = logging.getLogger(__name__)
INHERITANCE_ENTER_CODE = 1111

# ==============================================================
# 2. 功能处理器
# ==============================================================
def copy_inheritance_code(update: Update, context: CallbackContext) -> None:
    """当用户点击“复制继承码”按钮时触发"""
    query = update.callback_query
    query.answer("继承码已显示在下方，可直接复制！")  # 给用户一个即时反馈

    user_id = update.effective_user.id
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        if not user.inheritance_code:
            user.generate_inheritance_code()

        # 发送一条新消息，方便用户长按复制
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"这是你的继承码，请复制后发给要继承的人：\n<code>{user.inheritance_code}</code>",
            parse_mode='HTML'
        )
    except TelegramUser.DoesNotExist:
        query.edit_message_text(text="用户不存在。", reply_markup=append_back_button(None))


def refresh_inheritance_code(update: Update, context: CallbackContext) -> None:
    """刷新继承码"""
    query = update.callback_query
    query.answer("继承码已刷新！")

    user_id = update.effective_user.id
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        new_code = user.generate_inheritance_code()

        # 刷新后，更新整个消息的文本和按钮
        keyboard_buttons = [
            [single_button("📋 复制继承码", PREFIX_USER, "copy_inheritance_code")],
            [single_button("🔄 刷新继承码", PREFIX_USER, "refresh_inheritance_code")],
            [single_button("👤 使用继承码", PREFIX_USER, "use_inheritance_code")],
        ]
        reply_markup = append_back_button(keyboard_buttons)

        updated_message_text = (
            "🔗 <b>继承功能</b>\n\n"
            "你的继承码已成功刷新！\n\n"
            f"<code>{new_code}</code>\n\n"
            "点击「复制继承码」按钮可将新代码复制给接收方。"
        )

        query.edit_message_text(
            text=updated_message_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except TelegramUser.DoesNotExist:
        query.edit_message_text(text="用户不存在。", reply_markup=append_back_button(None))


def start_use_inheritance_code(update: Update, context: CallbackContext) -> int:
    """开始使用继承码的流程"""
    query = update.callback_query
    query.answer()

    # 发送提示消息，并附带返回按钮
    prompt_text = (
        "请输入你要继承的用户的 <b>继承码</b>：\n\n"
        "输入 /cancel 可取消当前操作。"
    )
    # 使用 append_back_button 确保在对话中也能返回主菜单
    reply_markup = append_back_button(None)

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=prompt_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return INHERITANCE_ENTER_CODE


def process_inheritance_code(update: Update, context: CallbackContext):
    """处理用户输入的继承码"""
    user_input_code = update.message.text.strip()
    receiver_user_id = update.effective_user.id

    # 验证输入格式
    try:
        inheritance_code = uuid.UUID(user_input_code)
    except ValueError:
        update.message.reply_text("❌ 无效的继承码格式，请输入正确的 UUID。")
        return INHERITANCE_ENTER_CODE

    try:
        with transaction.atomic():
            # 查找源用户并加锁
            source_user = TelegramUser.objects.select_for_update().get(inheritance_code=inheritance_code)

            # 查找接收用户并加锁
            receiver_user, _ = TelegramUser.objects.select_for_update().get_or_create(user_id=receiver_user_id)

            # 检查是否为同一人
            if source_user.user_id == receiver_user_id:
                update.message.reply_text("❌ 你不能继承自己的资产。")
                return end_all_conversations(context)

            # 执行继承逻辑
            # 假设你的 TelegramUser 模型有一个 inherit_from 方法
            receiver_user.inherit_from(source_user)

            # 发送成功消息
            update.message.reply_text(
                f"🎉 继承成功！\n\n"
                f"你已成功继承了其他用户的资产。\n"
                f"你的资产已更新！"
            )

    except TelegramUser.DoesNotExist:
        update.message.reply_text("❌ 未找到有效的继承码，或该继承码已被使用。")
        return INHERITANCE_ENTER_CODE
    except Exception as e:
        logger.error(f"继承过程中发生错误: {e}")
        update.message.reply_text(f"❌ 继承过程中发生错误: {e}")

    return end_all_conversations(context)


def cancel_inheritance(update: Update, context: CallbackContext):
    """取消继承操作"""
    update.message.reply_text("已取消继承操作。")
    return end_all_conversations(context)


# ==============================================================
# 3. ConversationHandler
# ==============================================================
def get_inheritance_conversation_handler() -> ConversationHandler:
    """创建并返回处理“使用继承码”流程的 ConversationHandler"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(
            start_use_inheritance_code,
            pattern=rf"^{PREFIX_USER}:use_inheritance_code$"
        )],
        states={
            INHERITANCE_ENTER_CODE: [
                MessageHandler(Filters.text & ~Filters.command, process_inheritance_code),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_inheritance),
            # 如果用户在对话中点击了返回主菜单按钮，也结束对话
        ],
        conversation_timeout=300,  # 5分钟无操作则自动取消
        per_user=True,
        per_chat=True,
        name="inheritance_conversation",
        persistent=False,
    )


# ==============================================================
# 4. 注册所有处理器
# ==============================================================
def register_inheritance_handlers(dispatcher):
    """向 dispatcher 注册所有与继承相关的处理器"""

    dispatcher.add_handler(CallbackQueryHandler(
        copy_inheritance_code,
        pattern=rf"^{PREFIX_USER}:copy_inheritance_code$"
    ))
    dispatcher.add_handler(CallbackQueryHandler(
        refresh_inheritance_code,
        pattern=rf"^{PREFIX_USER}:refresh_inheritance_code$"
    ))

    # 注册处理“使用继承码”的 ConversationHandler
    dispatcher.add_handler(get_inheritance_conversation_handler())
