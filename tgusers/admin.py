from django.contrib import admin
from django.utils import timezone
from .models import TelegramUser, UserGroupStats


# 注册内嵌模型：将UserGroupStats作为TelegramUser的内嵌表展示
class UserGroupStatsInline(admin.TabularInline):
    """内嵌展示用户的群聊统计数据"""
    model = UserGroupStats
    extra = 0  # 不显示额外的空白行
    verbose_name = "群聊统计"
    verbose_name_plural = "群聊统计数据"
    # 只读字段（根据需求调整）
    readonly_fields = ("daily_message_count", "daily_points_earned", "last_message_date")
    # 列表展示的字段
    fields = ("chat_id", "daily_message_count", "daily_points_earned", "last_message_date")

    def has_add_permission(self, request, obj=None):
        """禁止在后台手动添加群聊统计（由业务逻辑自动生成）"""
        return False


# 自定义TelegramUser的Admin配置
@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    """Telegram用户后台管理配置"""
    # 内嵌展示群聊统计数据
    inlines = [UserGroupStatsInline]

    # 列表页展示的字段
    list_display = (
        "user_id", "username", "first_name", "last_name",
        "points", "coins", "is_bot", "is_admin", "is_merchant",
        "has_interacted", "last_active_at", "created_at"
    )

    # 可搜索的字段
    search_fields = (
        "user_id", "username", "first_name", "last_name",
        "language_code"
    )

    # 侧边栏筛选条件
    list_filter = (
        "is_bot", "is_admin", "is_merchant",
        "has_interacted", "language_code",
        "created_at", "last_active_at", "last_sign_in_date"
    )

    # 只读字段（避免手动修改核心数据）
    readonly_fields = (
        "user_id", "created_at", "last_active_at",
        "last_sign_in_date"
    )

    # 编辑页的字段分组
    fieldsets = (
        ("用户基础信息", {
            "fields": ("user_id", "username", "first_name", "last_name", "is_bot", "language_code")
        }),
        ("资产与积分", {
            "fields": ("points", "coins")
        }),
        ("权限管理", {
            "fields": ("is_admin", "is_merchant", "is_super_admin")
        }),
        ("交互信息", {
            "fields": ("has_interacted", "last_sign_in_date", "created_at", "last_active_at")
        }),
    )

    # 列表页可直接编辑的字段（快速修改）
    list_editable = ("points", "coins", "is_admin", "is_merchant")

    # 排序方式
    ordering = ("-created_at", "-last_active_at")

    # 分页大小
    list_per_page = 20

    # 最大展示数量（避免性能问题）
    list_max_show_all = 1000

    def has_delete_permission(self, request, obj=None):
        """
        控制删除权限：仅超级管理员可删除用户
        可根据实际需求调整（如禁止删除任何用户）
        """
        return request.user.is_superuser


# 单独注册UserGroupStats（如需独立管理）
@admin.register(UserGroupStats)
class UserGroupStatsAdmin(admin.ModelAdmin):
    """用户群聊统计后台管理配置"""
    # 列表页展示字段
    list_display = (
        "id", "user", "chat_id", "daily_message_count",
        "daily_points_earned", "last_message_date"
    )

    # 搜索字段
    search_fields = ("user__user_id", "user__username", "chat_id")

    # 筛选条件
    list_filter = ("last_message_date",)

    # 只读字段（统计数据由业务逻辑自动生成，禁止手动修改）
    readonly_fields = (
        "user", "chat_id", "daily_message_count",
        "daily_points_earned", "last_message_date"
    )

    # 排序方式
    ordering = ("-last_message_date",)

    # 分页大小
    list_per_page = 20

    def has_add_permission(self, request):
        """禁止手动添加统计数据"""
        return False

    def has_delete_permission(self, request, obj=None):
        """仅超级管理员可删除统计数据"""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """禁止手动修改统计数据"""
        return False

