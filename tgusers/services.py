import datetime
from datetime import date
from django.utils import timezone

from django.db import models


from botconfig.services import get_bot_config
from tgusers.models import TelegramUser, UserGroupStats


def update_or_create_user(tg_user):
    obj, created = TelegramUser.objects.update_or_create(
        user_id=tg_user.id,
        defaults={
            "username": tg_user.username,
            "first_name": tg_user.first_name,
            "last_name": tg_user.last_name,
            "is_bot": tg_user.is_bot,
            "language_code": getattr(tg_user, "language_code", None),
            "has_interacted": True,  # 只要使用机器人就标记
        }
    )
    return obj


def add_points(user_id, amount):
    TelegramUser.objects.filter(user_id=user_id).update(
        points=models.F("points") + amount
    )


def process_sign_in(user: TelegramUser):

    config = get_bot_config()
    today = timezone.localdate()
    print("用户最后签到日期", user.last_sign_in_date, today)
    if user.last_sign_in_date == today:
        return False, "今天已经签到过了"

    user.last_sign_in_date = today
    user.points += config.sign_in_points
    user.save()  # 不要用 update_fields

    return True, f"签到成功，获得 {config.sign_in_points} 积分"



def add_coins(user_id, amount=1):
    TelegramUser.objects.filter(user_id=user_id).update(coins=models.F("coins") + amount)


def mark_user_interacted(user):
    if not user.has_interacted:
        user.has_interacted = True
        user.save(update_fields=["has_interacted"])


def get_or_create_group_stats(user: TelegramUser, chat_id: int):
    stats, created = UserGroupStats.objects.get_or_create(
        user=user,
        chat_id=chat_id
    )

    # 每日重置
    today = timezone.localdate()
    if stats.last_message_date != today:
        stats.daily_message_count = 0
        stats.daily_points_earned = 0
        stats.last_message_date = today
        stats.save(update_fields=["daily_message_count", "daily_points_earned", "last_message_date"])

    return stats


def process_message_points(user: TelegramUser, chat_id: int, text: str):
    """处理发言积分逻辑（按群独立计算）"""

    config = get_bot_config()
    stats = get_or_create_group_stats(user, chat_id)

    # 不够长度不给积分
    if len(text.strip()) < config.message_min_length:
        return 0

    # 达到每日上限
    if stats.daily_points_earned >= config.message_daily_limit:
        return 0

    # 基础积分
    points = config.message_base_points

    # 暴击
    import random
    if random.random() < config.crit_rate:
        points *= config.crit_multiplier

    # 更新统计
    stats.daily_message_count += 1
    stats.daily_points_earned += points
    stats.save(update_fields=["daily_message_count", "daily_points_earned"])

    # 更新用户总积分
    TelegramUser.objects.filter(id=user.id).update(points=models.F("points") + points)

    return points
