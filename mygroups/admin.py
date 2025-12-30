# mygroups/admin_review.py
from django.contrib import admin
from mygroups.models import MyGroup

@admin.register(MyGroup)  # 装饰器方式注册，与 admin.site.register 等效
class MyGroupAdmin(admin.ModelAdmin):
    # 列表页展示的字段
    list_display = (
        'group_chat_id',
        'group_username',
        'main_channel_id',
        'report_channel_id',
        'notify_channel_id',
        'created_at'
    )
    # 可搜索的字段
    search_fields = ('group_chat_id', 'group_username')
    # 按创建时间筛选
    list_filter = ('created_at',)
    # 只读字段（自动生成的时间字段设为只读）
    readonly_fields = ('created_at', 'updated_at')
