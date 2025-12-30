from django.db import models
from django.utils import timezone
import uuid
from tgusers.models import TelegramUser

def generate_verification_code():
    """生成一个16位的唯一核销码"""
    return str(uuid.uuid4()).replace("-", "")[:16]

class MallProduct(models.Model):
    """积分商城商品模型"""
    name = models.CharField(max_length=200, verbose_name="商品名称")
    description = models.TextField(verbose_name="商品描述")
    points_needed = models.IntegerField(default=0, verbose_name="所需积分")
    coins_needed = models.IntegerField(default=0, verbose_name="所需金币")
    stock = models.IntegerField(default=0, verbose_name="库存数量")
    is_active = models.BooleanField(default=True, verbose_name="是否上架")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def cost_text(self):
        if self.points_needed > 0:
            return f"{self.points_needed} 积分"
        return f"{self.coins_needed} 金币"

    def __str__(self):
        return f"{self.name}（{self.cost_text()}）"

    class Meta:
        verbose_name = "商城商品"
        verbose_name_plural = "商城商品"

class RedemptionRecord(models.Model):
    """兑换记录模型"""
    REDEMPTION_STATUS = (
        ("pending", "待核销"),
        ("used", "已核销"),
        ("expired", "已过期"),
    )
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="redemptions", verbose_name="兑换用户")
    product = models.ForeignKey(MallProduct, on_delete=models.CASCADE, related_name="redemptions", verbose_name="兑换商品")
    verification_code = models.CharField(max_length=32, unique=True, verbose_name="核销码", default=generate_verification_code)
    status = models.CharField(max_length=20, choices=REDEMPTION_STATUS, default="pending", verbose_name="状态")
    redeemed_at = models.DateTimeField(auto_now_add=True, verbose_name="兑换时间")
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="核销时间")
    verified_by = models.BigIntegerField(null=True, blank=True, verbose_name="核销管理员ID")

    def __str__(self):
        return f"{self.user.username} - {self.product.name} - {self.verification_code}"

    class Meta:
        verbose_name = "兑换记录"
        verbose_name_plural = "兑换记录"
