from django.apps import AppConfig


class TgfuncCarouselConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tgfunc_carousel'

    def ready(self):
        # 确保信号注册
        import tgfunc_carousel.signals