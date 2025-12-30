# places/models.py
from django.db import models

class Place(models.Model):
    name = models.CharField("场所名", max_length=200)
    short_name = models.CharField("场所简称", max_length=100, blank=True)
    city = models.CharField("城市", max_length=100)
    district = models.CharField("区域", max_length=100, blank=True)
    address = models.CharField("地址", max_length=300, blank=True)
    exchange_points = models.PositiveIntegerField("兑换所需积分", default=0, help_text="0 表示不可兑换")
    description = models.TextField("简介", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "场所"
        verbose_name_plural = "场所"

    def __str__(self):
        return self.short_name or self.name


class Marketing(models.Model):
    place = models.ForeignKey(
        "Place",
        on_delete=models.CASCADE,
        related_name="marketings"
    )
    name = models.CharField("营销名", max_length=120)
    phone = models.CharField("电话", max_length=50, blank=True)
    wechat = models.CharField("微信", max_length=100, blank=True)
    note = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    # 新增图片字段
    qr_or_screenshot = models.ImageField(
        "二维码/微信截图",
        upload_to="marketing/qrcodes/",   # 存储目录
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "场所营销"
        verbose_name_plural = "场所营销"
        unique_together = ("place", "name")

    def __str__(self):
        return f"{self.name} @ {self.place}"



class Staff(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="staffs")
    nickname = models.CharField("号码/昵称", max_length=120)
    is_active = models.BooleanField("在职/可用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "服务人员"
        verbose_name_plural = "服务人员"
        indexes = [
            models.Index(fields=["place", "nickname"]),
        ]

    def __str__(self):
        return self.nickname or self.code or f"Staff {self.id}"
