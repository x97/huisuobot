# lottery/services/notify_service.py

import threading
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from django.conf import settings
from telegram.utils.request import Request

from tgusers.models import TelegramUser


def get_bot():
    request = Request(**(getattr(settings, 'PROXY_SETTINGS', {}) or {}))
    return Bot(token=settings.TELEGRAM_BOT_TOKEN, request=request)


def notify_user_prize(user, prize, lottery):
    """给中奖用户发私信"""
    bot = get_bot()

    text = (
        f"🎉 恭喜你中奖啦！\n\n"
        f"活动：{lottery.title}\n"
        f"奖品：{prize.name}\n\n"
        f"兑奖说明：\n{lottery.description}"
    )

    try:
        bot.send_message(chat_id=user.user_id, text=text, parse_mode="Markdown")
    except TelegramError:
        pass


def notify_user_prize_async(user, prize, lottery):
    """异步发送"""
    threading.Thread(
        target=notify_user_prize,
        args=(user, prize, lottery),
        daemon=True
    ).start()


def notify_admins(result_message):
    """给所有管理员发开奖结果"""
    bot = get_bot()
    admins = TelegramUser.objects.filter(is_admin=True)

    for admin in admins:
        try:
            bot.send_message(chat_id=admin.user_id, text=result_message, parse_mode="Markdown")
        except:
            pass


def update_group_after_draw(lottery, result_message):
    """群里更新开奖消息"""
    bot = get_bot()

    ended_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 抽奖已结束", callback_data="action_lottery_ended")]
    ])

    # 修改原按钮
    try:
        bot.edit_message_reply_markup(
            chat_id=lottery.group_id,
            message_id=lottery.group_message_id,
            reply_markup=ended_btn
        )
    except:
        pass

    # 取消置顶
    try:
        bot.unpin_chat_message(
            chat_id=lottery.group_id,
            message_id=lottery.group_message_id
        )
    except:
        pass

    # 发送开奖结果并置顶
    try:
        sent = bot.send_message(
            chat_id=lottery.group_id,
            text=result_message,
            parse_mode="Markdown"
        )
        bot.pin_chat_message(
            chat_id=lottery.group_id,
            message_id=sent.message_id,
            disable_notification=True
        )
    except:
        pass




def send_lottery_to_group(context, lottery):
    """
    向配置的群聊发送抽奖通知，并将其置顶。
    :param context: 上下文对象
    :param lottery: 已保存的 Lottery 实例
    """
    chat_id = lottery.group_id
    if not chat_id:
        print("未指定目标群组 chat_id，发布失败")
        return

    # 2. 构建群通知内容 (Markdown 格式)
    prizes_text = "\n".join([f"• {p.name}（{p.quantity}份）" for p in lottery.prizes.all()])
    notification_text = f"""
🎉 **【群内积分抽奖】** 🎉

📢 抽奖标题：{lottery.title}
🎮 参与条件：{lottery.required_points} 积分
⏰ 开奖时间：{lottery.end_time.strftime('%Y-%m-%d %H:%M')}

🎁 奖品列表：
{prizes_text}

📝 兑奖说明：{lottery.description[:50]}...

👉 点击下方按钮立即参与，消耗 {lottery.required_points} 积分 即有机会中奖！
    """

    # 3. 构建“立即参与” Inline 按钮
    # 3. 构建“立即参与” Inline 按钮
    inline_keyboard = [
        [InlineKeyboardButton(f"🎯 立即参与（{lottery.required_points} 积分）", callback_data=f"lottery:join:{lottery.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)

    # 4. 发送消息并获取消息 ID，然后置顶
    try:
        # 发送消息
        sent_message = context.bot.send_message(
            chat_id=chat_id,
            text=notification_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        # 记录消息ID和群ID到 Lottery 实例
        lottery.group_message_id = sent_message.message_id
        lottery.save()  # 保存更改

        # 使用发送消息后返回的 `sent_message` 对象来获取 `message_id` 并置顶
        context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=sent_message.message_id,
            disable_notification=True  # 置顶时不发送通知，避免打扰所有人
        )
        print(f"成功向群 {chat_id} 发送并置顶了抽奖消息。")

    except Exception as e:
        # 错误处理，例如机器人没有置顶权限等
        print(f"向群 {chat_id} 发送或置顶消息失败：{str(e)}")
