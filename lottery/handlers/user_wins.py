# lottery/handlers/user_wins.py

from telegram.ext import CommandHandler
from django.utils import timezone
from datetime import timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from tgusers.services import update_or_create_user
from lottery.models import LotteryWinner
from lottery.constant import PREFIX_USER, PREFIX_ADMIN

def my_wins(update, context):
    # 判断是 command 还是 callback
    if update.callback_query:
        query = update.callback_query
        query.answer()
        tguser = update_or_create_user(query.from_user)
        reply = query.message.reply_text
    else:
        tguser = update_or_create_user(update.effective_user)
        reply = update.message.reply_text

    # 最近 30 天
    one_month_ago = timezone.now() - timedelta(days=30)
    wins = LotteryWinner.objects.filter(
        user=tguser,
        created_at__gte=one_month_ago
    ).select_related("lottery", "prize")

    # 如果 30 天没有 → 自动查 90 天
    if not wins.exists():
        three_months_ago = timezone.now() - timedelta(days=90)
        wins = LotteryWinner.objects.filter(
            user=tguser,
            created_at__gte=three_months_ago
        ).select_related("lottery", "prize")

        if not wins.exists():
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回主菜单", callback_data="core:back_main")]
            ])
            reply(
                "😔 最近三个月都没有中奖记录\n继续加油参与抽奖吧～",
                reply_markup=keyboard
            )
            return

        reply("📅 最近 30 天无中奖记录，以下是最近 3 个月的中奖记录：\n")

    # 构建展示内容
    text = "🎉 你的中奖记录：\n\n"
    for w in wins:
        text += (
            f"• **{w.lottery.title}**\n"
            f"  🎁 奖品：{w.prize.name}\n"
            f"  📅 时间：{w.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="core:back_main")]
    ])

    reply(text, parse_mode="Markdown", reply_markup=keyboard)


def register_user_wins_handlers(dp):
    dp.add_handler(CommandHandler("mywins", my_wins))
    dp.add_handler(CallbackQueryHandler(my_wins, pattern=r"^lottery_user:wins$"))
