from django.db import models
from django.utils import timezone
from tgusers.models import TelegramUser


class Report(models.Model):
    """
    用户报告/投诉模型（不再记录 merchant_username 与 merchant）
    仅记录提交者、内容、图片、审核信息与积分等
    """
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已驳回'),
    )

    reporter = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='submitted_reports',
        verbose_name='报告提交者',
        to_field='user_id',
        db_column='reporter_user_id'
    )
    place_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='场所名'
    )
    content = models.TextField(verbose_name='报告内容')

    image = models.ImageField(
        upload_to='report_images/',
        null=True,
        blank=True,
        verbose_name='报告图片'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='报告状态'
    )

    reviewed_by = models.ForeignKey(
        TelegramUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports',
        verbose_name='审核人',
        to_field='user_id',
        db_column='reviewed_by_user_id'
    )
    review_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_note = models.TextField(null=True, blank=True, verbose_name='审核备注')

    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='发布日期'
    )

    point = models.IntegerField(default=0, verbose_name='报告积分')

    class Meta:
        verbose_name = '用户报告'
        verbose_name_plural = '用户报告'
        ordering = ['-created_at']

    def __str__(self):
        return f"报告 #{self.id} - {self.reporter.user_id}"
