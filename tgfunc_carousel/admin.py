from django.contrib import admin
from .models import CarouselConfig, CarouselButton


@admin.register(CarouselConfig)
class CarouselConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "chat_id", "function_name", "interval", "page_size", "is_active", "updated_at")
    list_filter = ("is_active", "is_pinned", "delete_previous")
    search_fields = ("name", "function_name", "chat_id")
    ordering = ("-updated_at",)
    readonly_fields = ("last_message_id", "last_sent_at", "total_sent_count", "updated_at")


@admin.register(CarouselButton)
class CarouselButtonAdmin(admin.ModelAdmin):
    list_display = ("text", "type", "url", "callback_data")
    search_fields = ("text", "url", "callback_data")
