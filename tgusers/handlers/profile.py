# tgusers/handlers/profile.py
import logging
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler

from tgusers.models import TelegramUser
from common.callbacks import make_cb
from common.keyboards import append_back_button

logger = logging.getLogger(__name__)

PREFIX = "user_profile"
def user_profile(update: Update, context: CallbackContext):
    """用户查看自己的积分、金币、签到日期"""
    query = update.callback_query
    is_callback = query is not None

    # 统一回复函数
    def send(text, reply_markup):
        if is_callback:
            query.edit_message_text(text, parse_mode="HTML",reply_markup=reply_markup)
        else:
            update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

    # Telegram 用户对象
    tg = update.effective_user

    # 数据库用户对象
    tg_user = TelegramUser.objects.filter(user_id=tg.id).first()

    if not tg_user:
        send("未找到用户信息，请先与 bot 交互。")
        return

    # 格式化签到日期
    last_sign = (
        tg_user.last_sign_in_date.strftime("%Y-%m-%d")
        if tg_user.last_sign_in_date
        else "无记录"
    )

    # Telegram 名字处理
    full_name = tg.full_name or tg.first_name or "未知"
    username = f"@{tg.username}" if tg.username else "无"

    # 展示内容
    text = (
        "👤 <b>我的账户信息</b>\n\n"
        f"🆔 <b>用户ID：</b>{tg.id}\n"
        f"🙋‍♂️ <b>名字：</b>{full_name}\n"
        f"💬 <b>用户名：</b>{username}\n\n"
        f"💰 <b>积分：</b>{tg_user.points}\n"
        f"🪙 <b>金币：</b>{tg_user.coins}\n"
        f"📅 <b>最后签到：</b>{last_sign}\n"
    )

    send(text,reply_markup = append_back_button(None))



def register_user_profile_handlers(dispatcher):
    """注册用户账户信息相关 handlers"""
    dispatcher.add_handler(CommandHandler("my_profile", user_profile))

    dispatcher.add_handler(CallbackQueryHandler(
        user_profile,
        pattern=r"^user_profile:show$"
    ))
