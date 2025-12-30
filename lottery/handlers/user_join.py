# lottery/handlers/user_join.py

from telegram.ext import CallbackQueryHandler
from django.utils import timezone
from tgusers.services import update_or_create_user
from lottery.models import Lottery, LotteryParticipant


def handle_join_lottery(update, context):
    query = update.callback_query
    query.answer()

    # callback_data 格式： lottery:join:<id>
    parts = query.data.split(":")
    lottery_id = int(parts[-1])

    try:
        lottery = Lottery.objects.get(id=lottery_id)
    except Lottery.DoesNotExist:
        query.message.reply_text("❌ 抽奖不存在或已被删除")
        return

    # 检查是否已结束
    if lottery.is_drawn or not lottery.is_active:
        query.message.reply_text("🎬 该抽奖已结束，无法参与")
        return

    # 检查是否过期
    if timezone.now() > lottery.end_time:
        query.message.reply_text("⏰ 抽奖已截止，无法参与")
        return

    # 获取用户
    user = update_or_create_user(update.effective_user)

    # 计算折扣后的积分
    required = lottery.required_points

    if user.points < required:
        query.message.reply_text(
            f"❌ 积分不足，需要 {required} XP，你当前 {user.points} XP"
        )
        return

    # 扣积分
    user.points -= required
    user.save()

    # 记录参与
    LotteryParticipant.objects.create(lottery=lottery, user=user)

    # 统计参与次数
    total_participations = LotteryParticipant.objects.filter(lottery=lottery, user=user).count()

    msg = (
        f"🎉 参与成功！\n"
        f"你已参与 {total_participations} 次\n"
        f"已扣除 {required} XP，剩余 {user.points} XP"
    )

    query.message.reply_text(msg)


def register_user_join_handlers(dp):
    dp.add_handler(
        CallbackQueryHandler(handle_join_lottery, pattern=r"^lottery:join:\d+$")
    )
