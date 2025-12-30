# tgusers/admin_review.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Report
from tgusers.models import  TelegramUser
from django.utils import timezone

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """用户报告管理后台配置"""
    # 列表页显示的字段
    list_display = [
        'id', 'status', 'reporter_link', 'image_thumbnail', 'point',
        'created_at', 'reviewed_by', 'review_time'
    ]
    readonly_fields = ('show_reporter',)  # 设为只读，避免编辑
    # 快速筛选器
    list_filter = ['status', 'created_at', 'review_time']

    # 搜索字段（支持报告提交者、商家用户名、报告内容搜索）
    search_fields = [
        'reporter__user_id', 'reporter__first_name', 'reporter__username',
        'content', 'review_note'
    ]

    # 排序规则（默认按创建时间倒序）
    ordering = ['-created_at']

    # 分页大小
    list_per_page = 20

    # 详情页字段分组
    fieldsets = (
        ('报告基本信息', {
            'fields': ('reporter', 'content', 'image', 'point')
        }),
        ('审核状态管理', {
            'fields': ('status', 'reviewed_by', 'review_time', 'review_note'),
            'classes': ('collapse',)  # 可折叠分组
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',),
            'description': '系统自动生成的信息，不可修改'
        }),
    )

    # 只读字段（系统自动生成的字段）
    readonly_fields = ['created_at', 'review_time']

    def reporter_link(self, obj):
        # 1. 生成报告列表的Admin路由（替换app名为你的实际应用名）
        report_list_url = reverse('admin:reports_report_change',   args=[obj.id]  )
        # 2. 拼接过滤参数，仅显示当前提交者的报告
        filtered_url = f"{report_list_url}"
        # 3. 生成HTML链接，显示提交者用户名
        return format_html(
            '<a href="{}" target="_blank">{}</a>',  # target="_blank" 新窗口打开
            filtered_url,
            obj.reporter.username
        )

    reporter_link.short_description = '报告提交者'  # 字段标题

    # 自定义字段：显示报告提交者完整信息
    def reporter_info(self, obj):
        """显示提交者的用户ID和昵称（点击可跳转到用户详情页）"""
        if obj.reporter:
            # 错误写法: user_url = reverse('admin:tgusers_telegramuser_change', args=[obj.reporter.id])
            # 正确写法: 使用 user_id 作为参数
            user_url = reverse('admin:tgusers_telegramuser_change', args=[obj.reporter.user_id])
            return format_html(
                '<a href="{}" target="_blank">{}（ID: {}）</a>',
                user_url,
                obj.reporter.first_name or obj.reporter.username or '未知用户',
                obj.reporter.user_id # 这里也用 user_id
            )
        return '未知提交者'
    reporter_info.short_description = '报告提交者'
    # 排序字段也需要更新
    reporter_info.admin_order_field = 'reporter__user_id'

    # 自定义字段：显示图片缩略图
    def image_thumbnail(self, obj):
        """在列表页显示图片缩略图（点击可查看原图）"""
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(
                '<img src="{}" style="width: 60px; height: auto;" title="点击查看原图" '
                'onclick="window.open(\'{}\', \'_blank\')">',
                obj.image.url,
                obj.image.url
            )
        return '无图片'

    image_thumbnail.short_description = '报告图片'
    image_thumbnail.allow_tags = True  # 允许HTML标签

    # 保存时自动填充审核时间
    def save_model(self, request, obj, form, change):
        """保存模型时的钩子函数：更新审核时间和审核人"""
        # 如果是修改报告，且状态发生变化/审核人变更，自动更新审核时间
        if change:
            old_obj = Report.objects.get(pk=obj.pk)
            # 状态变更或审核人变更时，更新审核信息
            if (obj.status != old_obj.status) or (obj.reviewed_by != old_obj.reviewed_by):
                obj.review_time = timezone.now()
                # 如果未指定审核人，默认设为当前登录管理员（需确保管理员关联了TelegramUser）
                if not obj.reviewed_by:
                    try:
                        obj.reviewed_by = TelegramUser.objects.get(user_id=request.user.id)
                    except TelegramUser.DoesNotExist:
                        pass
        super().save_model(request, obj, form, change)

    # 批量操作：批量设置为"已通过"
    def mark_approved(self, request, queryset):
        """批量将选中报告设为已通过"""
        self._update_report_status(request, queryset, 'approved', '已通过')

    mark_approved.short_description = '批量设为【已通过】'

    # 批量操作：批量设置为"已驳回"
    def mark_rejected(self, request, queryset):
        """批量将选中报告设为已驳回"""
        self._update_report_status(request, queryset, 'rejected', '已驳回')

    mark_rejected.short_description = '批量设为【已驳回】'

    # 批量操作：批量设置为"待审核"
    def mark_pending(self, request, queryset):
        """批量将选中报告设为待审核"""
        self._update_report_status(request, queryset, 'pending', '待审核')

    mark_pending.short_description = '批量设为【待审核】'

    # 批量操作辅助函数
    def _update_report_status(self, request, queryset, status, status_name):
        """更新报告状态的通用函数"""
        try:
            admin_user = TelegramUser.objects.get(user_id=request.user.id)
        except TelegramUser.DoesNotExist:
            self.message_user(request, f'错误：当前管理员未关联Telegram用户，无法更新审核人', level='error')
            return

        updated_count = queryset.update(
            status=status,
            reviewed_by=admin_user,
            review_time=timezone.now()
        )
        self.message_user(request, f'成功将 {updated_count} 条报告设为【{status_name}】')

    # 注册批量操作
    actions = ['mark_approved', 'mark_rejected', 'mark_pending']

    # 优化ForeignKey选择框（只显示相关用户）
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """自定义外键字段的选择框选项"""
        if db_field.name == 'reporter':
            # 只显示有提交过报告的用户
            kwargs['queryset'] = TelegramUser.objects.filter(submitted_reports__isnull=False).distinct()
        elif db_field.name == 'reviewed_by':
            # 只显示系统内的管理员用户（is_admin=True）
            kwargs['queryset'] = TelegramUser.objects.filter(is_admin=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
