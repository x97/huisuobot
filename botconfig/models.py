from django.db import models


class BotConfig(models.Model):
    """机器人动态配置参数（单例）"""

    sign_in_keywords = models.TextField(default="签到")
    sign_in_points = models.IntegerField(default=10)

    message_min_length = models.IntegerField(default=10)
    message_base_points = models.IntegerField(default=2)
    message_daily_limit = models.IntegerField(default=50)

    crit_rate = models.FloatField(default=0.1)
    crit_multiplier = models.IntegerField(default=2)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # 保存后更新缓存
        from botconfig.services import refresh_bot_config_cache
        refresh_bot_config_cache()

    @staticmethod
    def get_solo():
        """获取唯一配置，没有则创建"""
        obj, created = BotConfig.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return "BotConfig (singleton)"
