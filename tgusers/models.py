from django.db import models
import uuid


class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)

    points = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)
    experiences = models.IntegerField(default=0, verbose_name="经验值")

    is_bot = models.BooleanField(default=False)
    language_code = models.CharField(max_length=10, null=True, blank=True)

    last_active_at = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    is_admin = models.BooleanField(default=False, verbose_name="是否为管理员")
    is_merchant = models.BooleanField(default=False, verbose_name="是否为商家")
    is_super_admin = models.BooleanField(default=False, verbose_name="是否为超级管理员")
    has_interacted = models.BooleanField(default=False, verbose_name="是否有过交互")
    inheritance_code = models.UUIDField(
        default=None,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        verbose_name="继承码"
    )
    last_sign_in_date = models.DateField(null=True, blank=True, verbose_name="最后签到日期")

    def __str__(self):
        return f"{self.user_id} ({self.username})"


    def generate_inheritance_code(self):
        """生成一个新的、唯一的继承码"""
        # 使用 uuid4() 生成一个随机的 UUID

        self.inheritance_code = uuid.uuid4()
        self.save(update_fields=['inheritance_code'])
        return self.inheritance_code

    def inherit_from(self, source_user):
        """
        从另一个用户（source_user）继承资产。
        1. 将 source_user 的指定字段值复制到当前用户。
        2. 调用 source_user 的 clear_inheritance_code() 方法，
           该方法会自动将 source_user 的资产清零并清除其继承码。
        """
        # 定义需要继承的字段列表
        fields_to_inherit = [
            'coins', 'points', 'experiences',
        ]

        # 复制值
        for field in fields_to_inherit:
            setattr(self, field, getattr(source_user, field))

        # 保存当前用户的新值
        self.save(update_fields=fields_to_inherit)

        # 关键改动：调用 source_user 的 clear_inheritance_code() 方法
        # 这会同时清零源用户的资产并清除其继承码
        source_user.clear_inheritance_code()

        return True

class UserGroupStats(models.Model):
    """用户在每个群的独立统计数据"""

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="group_stats")
    chat_id = models.BigIntegerField(db_index=True)

    daily_message_count = models.IntegerField(default=0)
    daily_points_earned = models.IntegerField(default=0)
    last_message_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "chat_id")

    def __str__(self):
        return f"Stats: user={self.user_id} chat={self.chat_id}"
