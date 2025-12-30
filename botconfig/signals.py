from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from botconfig.models import BotConfig
from botconfig.services import refresh_bot_config_cache


@receiver(post_save, sender=BotConfig)
def refresh_cache_on_save(sender, instance, **kwargs):
    """
    当 BotConfig 被保存时，自动刷新缓存
    """
    refresh_bot_config_cache()


@receiver(post_delete, sender=BotConfig)
def refresh_cache_on_delete(sender, instance, **kwargs):
    """
    理论上不会删除，但如果删除了，也刷新缓存
    """
    refresh_bot_config_cache()
