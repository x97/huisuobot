# admin_review.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Place, Marketing, Staff,PlaceFormerName


class MarketingInline(admin.TabularInline):
    model = Marketing
    extra = 1  # 默认显示1个空表单
    max_num = 10  # 最多允许10个营销联系人
    fields = ('name', 'phone', 'wechat', 'note', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    # 紧凑显示，减少表单高度
    classes = ('collapse',)  # 可折叠


class StaffInline(admin.TabularInline):
    model = Staff
    extra = 1
    max_num = 50  # 最多允许50个服务人员
    fields = ('nickname', 'is_active', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-is_active', 'nickname')


class PlaceFormerNameInline(admin.TabularInline):
    model = PlaceFormerName
    extra = 1
    fields = ("name", "short_name", "first_letter", "created_at")
    readonly_fields = ("created_at",)



@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    # 列表页显示
    list_display = ('id', 'name', 'short_name', 'city', 'district',
                    'exchange_points_display', 'marketing_count',
                    'staff_count', 'active_staff_count', 'created_at')
    list_display_links = ('id', 'name')
    list_filter = ('city', 'district', 'created_at')
    search_fields = ('name', 'short_name', 'city', 'district', 'address')
    list_per_page = 20

    # 详情页字段分组
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'short_name', 'first_letter','city', 'district', 'address')
        }),
        ('积分与描述', {
            'fields': ('exchange_points', 'description'),
            'classes': ('wide',),
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # 内联模型
    inlines = [MarketingInline, StaffInline, PlaceFormerNameInline]

    readonly_fields = ('created_at', 'updated_at')

    # 自定义方法用于列表显示
    def exchange_points_display(self, obj):
        if obj.exchange_points == 0:
            return format_html('<span style="color:gray;">不可兑换</span>')
        return format_html('<span style="color:green; font-weight:bold;">{} 积分</span>',
                           obj.exchange_points)

    exchange_points_display.short_description = "兑换积分"

    def marketing_count(self, obj):
        count = obj.marketings.count()
        return format_html('<span style="color:blue;">{}</span>', count)

    marketing_count.short_description = "营销人数"

    def staff_count(self, obj):
        count = obj.staffs.count()
        return format_html('<span style="color:purple;">{}</span>', count)

    staff_count.short_description = "总人员"

    def active_staff_count(self, obj):
        count = obj.staffs.filter(is_active=True).count()
        color = "green" if count > 0 else "red"
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, count)

    active_staff_count.short_description = "在职人员"

    # 保存时自动设置短名称
    def save_model(self, request, obj, form, change):
        if not obj.short_name:
            obj.short_name = obj.name[:30]  # 取前30个字符作为短名称
        super().save_model(request, obj, form, change)


@admin.register(Marketing)
class MarketingAdmin(admin.ModelAdmin):
    # 也可以单独注册，方便单独查看所有营销人员
    list_display = ('id', 'name', 'place', 'phone', 'wechat', 'created_at')
    list_display_links = ('id', 'name')
    list_filter = ('place__city', 'created_at')
    search_fields = ('name', 'phone', 'wechat', 'place__name', 'note')
    list_select_related = ('place',)
    list_per_page = 20

    fields = ('place', 'name', 'phone', 'wechat', 'note', 'created_at')
    readonly_fields = ('created_at',)

    # 自动完成，提高选择场所的效率
    autocomplete_fields = ['place']


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    """服务人员管理（最简洁、最专业版本）"""

    list_display = (
        'id',
        'nickname',
        'place',
        'is_active',
        'created_at',
    )
    list_display_links = ('id', 'nickname')

    list_filter = (
        'place',
        'is_active',
        'created_at',
    )

    search_fields = (
        'nickname',
        'place__name',
    )

    list_select_related = ('place',)
    list_per_page = 30

    # 详情页字段分组
    fieldsets = (
        ('基本信息', {
            'fields': ('place', 'nickname', 'is_active'),
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['place']




