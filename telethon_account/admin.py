# telethon_account/admin.py

from django.contrib import admin
from .models import TelethonAccount
from django.utils.translation import gettext_lazy as _

@admin.register(TelethonAccount)
class TelethonAccountAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'api_id', 'status', 'limited_until', 'updated_at')
    list_filter = ('status',)
    search_fields = ('phone_number', 'api_id', 'error_message')
    readonly_fields = ('session_string', 'created_at', 'updated_at', 'created_by')
    fieldsets = (
        (_('Account Information'), {
            'fields': ('phone_number', 'api_id', 'api_hash')
        }),
        (_('Session & Status'), {
            'fields': ('session_string', 'status', 'limited_until', 'error_message')
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        """在保存时自动设置创建者"""
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
