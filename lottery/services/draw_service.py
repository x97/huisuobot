# lottery/services/draw_service.py

import random
from django.utils import timezone
from lottery.models import Lottery, Prize, LotteryParticipant, LotteryWinner
from lottery.services.notify_service import (
    notify_user_prize_async,
    notify_admins,
    update_group_after_draw
)


def draw_lottery_and_notify(lottery_id):
    """开奖 + 通知"""
    try:
        lottery = Lottery.objects.get(id=lottery_id, is_active=True, is_drawn=False)
    except Lottery.DoesNotExist:
        print(f"❌ 抽奖 {lottery_id} 不存在或已开奖")
        return

    participants = list(LotteryParticipant.objects.filter(lottery=lottery))
    prizes = Prize.objects.filter(lottery=lottery)

    winners_text = []

    if not participants:
        result_message = f"🎬 抽奖【{lottery.title}】无人参与。"
    else:
        for prize in prizes:
            draw_count = min(prize.quantity, len(participants))
            selected = random.sample(participants, draw_count)

            for record in selected:
                LotteryWinner.objects.create(
                    lottery=lottery,
                    prize=prize,
                    user=record.user
                )
                notify_user_prize_async(record.user, prize, lottery)

            names = []
            for record in selected:
                u = record.user
                first = u.first_name or ""
                last = u.last_name or ""
                username = u.username

                # 拼接显示名
                display_name = f"【{(first + ' ' + last).strip()}】"
                if username:
                    display_name += f"@{username}"
                else:
                    display_name += f"(id:{u.user_id})"  # 没有 username 时用 id 兜底

                names.append(display_name)

            winners_text.append(f"✅{prize.name}：{', '.join(names)}")

        result_message = (
            f"🎬 抽奖【{lottery.title}】开奖结果\n\n"
            f"👥 参与人次：{len(participants)}\n\n"
            f"🎁 中奖名单：\n" + "\n".join(winners_text) + "\n\n"
            f"📝 兑奖说明：\n{lottery.description}"
        )

    # 更新状态
    lottery.is_drawn = True
    lottery.is_active = False
    lottery.result_message = result_message
    lottery.save()

    # 群里更新
    update_group_after_draw(lottery, result_message)

    # 管理员通知
    notify_admins(result_message)

    print(f"🎉 抽奖 {lottery.title} 已开奖")
