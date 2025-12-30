# mygroups/services.py

from django.core.cache import cache
from mygroups.models import MyGroup

CACHE_KEY = "mygroups_cache"
CACHE_TIMEOUT = 3600


def load_mygroups_cache():
    groups = MyGroup.objects.all()

    allowed_groups = set()
    allowed_channels = set()
    group_map = {}

    for g in groups:
        allowed_groups.add(g.group_chat_id)
        group_map[g.group_chat_id] = g

        if g.main_channel_id:
            allowed_channels.add(g.main_channel_id)
        if g.report_channel_id:
            allowed_channels.add(g.report_channel_id)
        if g.notify_channel_id:
            allowed_channels.add(g.notify_channel_id)

    data = {
        "allowed_groups": allowed_groups,
        "allowed_channels": allowed_channels,
        "group_map": group_map,
    }

    cache.set(CACHE_KEY, data, CACHE_TIMEOUT)
    return data


def get_mygroups_cache():
    data = cache.get(CACHE_KEY)
    if data is None:
        data = load_mygroups_cache()
    return data


def refresh_mygroups_cache():
    return load_mygroups_cache()

