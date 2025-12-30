# mygroups/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from mygroups.models import MyGroup
from mygroups.services import refresh_mygroups_cache


@receiver(post_save, sender=MyGroup)
@receiver(post_delete, sender=MyGroup)
def refresh_cache_on_change(sender, **kwargs):
    refresh_mygroups_cache()
