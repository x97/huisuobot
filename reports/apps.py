from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'
    def ready(self):
        # 确保信号被导入和注册（信号导入本身无数据库操作，可保留）
        import reports.signals