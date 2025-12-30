# models.py
from django.db import models
from django.utils import timezone
from tgusers.models import TelegramUser

class Lottery(models.Model):
    """积分抽奖活动模型"""
    title = models.CharField(max_length=200, verbose_name="抽奖标题")
    description = models.TextField(verbose_name="兑奖说明")
    required_points = models.IntegerField(verbose_name="参与所需积分")
    start_time = models.DateTimeField(default=timezone.now, verbose_name="活动开始时间")
    end_time = models.DateTimeField(verbose_name="开奖时间")
    is_active = models.BooleanField(default=True, verbose_name="是否正在进行")
    is_drawn = models.BooleanField(default=False, verbose_name="是否已开奖")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    result_message = models.TextField(blank=True, null=True, verbose_name="开奖结果消息")  # 存储开奖结果
    # 新增字段：存储群消息ID和群ID
    group_message_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="群消息ID"
    )
    group_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="发布的群ID"
    )

    class Meta:
        verbose_name = "抽奖活动"
        verbose_name_plural = "抽奖活动"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Prize(models.Model):
    """奖品模型"""
    lottery = models.ForeignKey(Lottery, related_name='prizes', on_delete=models.CASCADE, verbose_name="所属抽奖")
    name = models.CharField(max_length=100, verbose_name="奖品名称")
    quantity = models.IntegerField(verbose_name="奖品数量")

    class Meta:
        verbose_name = "奖品"
        verbose_name_plural = "奖品"

    def __str__(self):
        return f"{self.name} ({self.quantity}份)"


# models.py 新增
class LotteryParticipant(models.Model):
    """抽奖参与记录表"""
    lottery = models.ForeignKey(Lottery, related_name='participants', on_delete=models.CASCADE, verbose_name="所属抽奖")
    user = models.ForeignKey(TelegramUser, related_name='lottery_participations', on_delete=models.CASCADE, verbose_name="参与用户")
    participated_at = models.DateTimeField(auto_now_add=True, verbose_name="参与时间")

    class Meta:
        verbose_name = "抽奖参与记录"
        verbose_name_plural = "抽奖参与记录"

    def __str__(self):
        return f"{self.user.username or self.user.user_id} - {self.lottery.title}"


from tgusers.models import TelegramUser

class LotteryWinner(models.Model):
    """中奖记录模型"""
    lottery = models.ForeignKey(
        Lottery,
        on_delete=models.CASCADE,
        related_name='winners',
        verbose_name="所属抽奖"
    )
    prize = models.ForeignKey(
        Prize,
        on_delete=models.CASCADE,
        verbose_name="获得奖项"
    )
    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='lottery_wins',
        verbose_name="中奖用户"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="中奖时间"
    )

    class Meta:
        verbose_name = "中奖记录"
        verbose_name_plural = "中奖记录"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.prize.name}"

