from django.apps import AppConfig


class BotconfigConfig(AppConfig):
    name = 'botconfig'

    def ready(self):
        import botconfig.signals
