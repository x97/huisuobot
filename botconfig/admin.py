from django.contrib import admin
from botconfig.models import BotConfig


@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # 禁止创建多个
        return not BotConfig.objects.exists()
