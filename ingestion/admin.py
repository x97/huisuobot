from django.contrib import admin
from .models import IngestionSource


@admin.register(IngestionSource)
class IngestionSourceAdmin(admin.ModelAdmin):
    """
    IngestionSource 的专业管理后台
    """

    # 列表页显示字段
    list_display = (
        "id",
        "platform",
        "source_type",
        "channel_name",
        "channel_username",
        "channel_id",
        "data_type",
        "fetch_mode",
        "is_active",
        "last_message_id",
        "last_fetched_at",
    )

    # 可搜索字段
    search_fields = (
        "channel_name",
        "channel_username",
        "channel_id",
    )

    # 过滤器
    list_filter = (
        "platform",
        "source_type",
        "data_type",
        "fetch_mode",
        "is_active",
    )

    # 排序
    ordering = ("-created_at",)

    # 只读字段（不允许手动改抓取进度）
    readonly_fields = (
        "last_fetched_at",
        "created_at",
        "updated_at",
    )

    # 字段分组（让界面更清晰）
    fieldsets = (
        ("基础信息", {
            "fields": ("platform", "source_type", "is_active")
        }),
        ("Telegram 信息", {
            "fields": ("channel_id", "channel_username", "channel_name"),
            "description": "仅当平台为 Telegram 时有效"
        }),
        ("抓取配置", {
            "fields": ("data_type", "fetch_mode")
        }),
        ("抓取进度（自动更新）", {
            "fields": ("last_message_id", "last_fetched_at"),
        }),
        ("扩展配置", {
            "fields": ("extra_config",),
        }),
        ("系统字段", {
            "fields": ("created_at", "updated_at"),
        }),
    )
