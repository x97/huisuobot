from django.core.cache import cache
from botconfig.models import BotConfig

CACHE_KEY = "bot_config_cache"
CACHE_TIMEOUT = 60 * 60  # 1 hour


def get_bot_config():
    """从缓存获取配置，没有则加载数据库并写入缓存"""
    config = cache.get(CACHE_KEY)
    if config is None:
        config = BotConfig.get_solo()
        cache.set(CACHE_KEY, config, CACHE_TIMEOUT)
    return config


def refresh_bot_config_cache():
    """更新缓存"""
    config = BotConfig.get_solo()
    cache.set(CACHE_KEY, config, CACHE_TIMEOUT)
