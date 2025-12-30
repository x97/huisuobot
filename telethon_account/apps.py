# telethon_account/apps.py

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class TelethonAccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telethon_account'
    verbose_name = _('Telethon Accounts')

    def ready(self):
        """
        应用就绪时执行，可以在这里注册信号等。
        """
        pass
