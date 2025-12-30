# collect/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from places.models import Place

# 假设 MyGroup 在某处定义并包含 notify_channel_id 字段
# from groups.models import MyGroup

class Campaign(models.Model):
    title = models.CharField("悬赏标题", max_length=200)
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="campaigns")
    description = models.TextField("悬赏描述", blank=True)
    reward_coins = models.PositiveIntegerField("奖励金币", default=0)
    max_submissions = models.PositiveIntegerField("最大提交数", null=True, blank=True)
    start_at = models.DateTimeField("开始时间", default=timezone.now)
    end_at = models.DateTimeField("结束时间", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "悬赏活动"
        verbose_name_plural = "悬赏活动"

    def __str__(self):
        return f"{self.title} @ {self.place}"

class Submission(models.Model):
    STATUS_CHOICES = [
        ("pending", "待审核"),
        ("approved", "通过"),
        ("rejected", "不通过"),
    ]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True, blank=True)
    reporter = models.ForeignKey("tgusers.TelegramUser", on_delete=models.SET_NULL, null=True, blank=True)

    # 用户提交的详细信息（不进入 Staff）
    nickname = models.CharField("技师号码", max_length=200)
    birth_year = models.CharField("出生年份", null=True, blank=True, max_length=50)
    bust_size = models.CharField("胸围大小", max_length=50, blank=True)
    bust_info = models.CharField("胸围信息", max_length=240, blank=True)
    attractiveness = models.CharField("颜值评价", null=True, blank=True, max_length=120)
    extra_info = models.TextField("补充信息", blank=True)

    # 审核信息
    status = models.CharField("审核状态", max_length=10, choices=STATUS_CHOICES, default="pending")
    reviewer = models.ForeignKey("tgusers.TelegramUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    review_note = models.TextField("审核备注", blank=True)
    created_at = models.DateTimeField("提交时间", auto_now_add=True)
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)

    # 新增字段：关联最终员工档案
    staff = models.ForeignKey("places.Staff", null=True, blank=True, on_delete=models.SET_NULL, related_name="submissions")

    # 新增字段：员工离职后自动过期
    is_valid = models.BooleanField("是否有效", default=True)

    def __str__(self):
        return f"{self.nickname} ({self.get_status_display()})"


class SubmissionPhoto(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="photos"
    )
    image = models.ImageField(upload_to="submission_photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[("pending", "待审核"), ("approved", "通过"), ("rejected", "不通过")],
        default="pending"
    )
    review_note = models.TextField(blank=True)


class CampaignNotification(models.Model):
    """
    记录管理员发布悬赏时发送到通知频道的消息
    notify_channel_id 来自 MyGroup.notify_channel_id
    message_id 为 Telegram 返回的 message_id
    """
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="notifications")
    mygroup_id = models.IntegerField("MyGroup ID", null=True, blank=True)
    notify_channel_id = models.BigIntegerField("通知频道 chat_id")
    message_id = models.BigIntegerField("通知消息 message_id")
    created_at = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        verbose_name = "悬赏通知记录"
        verbose_name_plural = "悬赏通知记录"
        indexes = [
            models.Index(fields=["notify_channel_id", "message_id"]),
        ]

    def __str__(self):
        return f"Notify {self.campaign} -> {self.notify_channel_id}:{self.message_id}"



class ExchangeRecord(models.Model):
    STATUS_CHOICES = [
        ("completed", "已完成"),
        ("refunded", "已退回"),
        ("appealed", "申诉中"),
    ]
    user = models.ForeignKey("tgusers.TelegramUser", on_delete=models.SET_NULL, null=True, blank=True)
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True)
    marketing = models.ForeignKey("places.Marketing", on_delete=models.SET_NULL, null=True, blank=True)
    points = models.PositiveIntegerField("消耗积分")
    created_at = models.DateTimeField("兑换时间", auto_now_add=True)
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="completed")
    # 申诉字段
    appeal_reason = models.TextField("申诉理由", blank=True)
    appeal_at = models.DateTimeField("申诉时间", null=True, blank=True)
    refunded_at = models.DateTimeField("退回时间", null=True, blank=True)

    class Meta:
        verbose_name = "兑换记录"
        verbose_name_plural = "兑换记录"

    @property
    def status_show(self):
        d = {
            "completed": "已完成",
            "refunded": "已退回",
            "appealed": "申诉中"
        }
        return d.get(self.status)
