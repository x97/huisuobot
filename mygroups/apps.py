from django.apps import AppConfig


class MygroupsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mygroups'

    def ready(self):
        import mygroups.signals
