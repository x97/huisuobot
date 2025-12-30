from django.contrib import admin
from .models import Lottery, Prize, LotteryParticipant, LotteryWinner

class PrizeInline(admin.TabularInline):
    """
    奖品内嵌 Admin，用于在 Lottery 编辑页直接管理奖品
    """
    model = Prize
    extra = 1  # 默认显示 1 个额外的空白表单用于添加新奖品
    verbose_name = '奖品'
    verbose_name_plural = '奖品设置'


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    """
    抽奖活动 Admin 配置
    """
    # 列表页显示的字段
    list_display = ('title', 'required_points', 'start_time', 'end_time', 'is_active', 'is_drawn', 'participant_count')

    # 列表页可点击进入编辑的字段
    list_display_links = ('title',)

    # 列表页的筛选器
    list_filter = ('is_active', 'is_drawn')

    # 搜索框可搜索的字段
    search_fields = ('title', 'description')

    # 日期时间选择器

    # 编辑页的字段分组
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description', 'required_points')
        }),
        ('时间设置', {
            'fields': ('start_time', 'end_time')
        }),
        ('状态与结果', {
            'fields': ('is_active', 'is_drawn', 'result_message'),
            'classes': ('collapse',)  # 默认折叠
        }),
        ('群组信息 (内部使用)', {
            'fields': ('group_id', 'group_message_id'),
            'classes': ('collapse', 'wide'),  # 默认折叠，并且宽度自适应
            'description': '这些字段由机器人自动填充，通常不需要手动修改。'
        }),
    )

    # 在编辑页内嵌管理关联的 Prize
    inlines = [PrizeInline]

    def participant_count(self, obj):
        """
        自定义列表字段：显示参与人数
        """
        return obj.participants.count()

    participant_count.short_description = '参与人数'  # 列标题
    participant_count.admin_order_field = 'participants__count'  # 允许根据此字段排序



@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    """
    奖品 Admin 配置
    """
    list_display = ('name', 'lottery', 'quantity')
    list_filter = ('lottery',)
    search_fields = ('name', 'lottery__title')
    list_per_page = 20


@admin.register(LotteryParticipant)
class LotteryParticipantAdmin(admin.ModelAdmin):
    """
    抽奖参与记录 Admin 配置
    """
    list_display = ('id', 'lottery', 'user', 'participated_at')
    list_filter = ('lottery',)
    search_fields = ('user__username', 'user__user_id', 'lottery__title')
    list_per_page = 50


@admin.register(LotteryWinner)
class LotteryWinnerAdmin(admin.ModelAdmin):
    """
    中奖记录 Admin 配置
    """
    list_display = ('id', 'lottery', 'prize', 'user', 'created_at')
    list_filter = ('lottery', 'prize')
    search_fields = ('user__username', 'user__user_id', 'lottery__title', 'prize__name')
    list_per_page = 50
