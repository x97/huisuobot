# collect/admin_review.py
from django.contrib import admin
from django.utils import timezone

from .models import Campaign, Submission, CampaignNotification

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "place", "reward_coins", "is_active", "start_at", "end_at")
    search_fields = ("title", "place__name")
    actions = ["deactivate_campaign"]

    def deactivate_campaign(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_campaign.short_description = "禁用所选悬赏"


@admin.register(CampaignNotification)
class CampaignNotificationAdmin(admin.ModelAdmin):
    list_display = ("campaign", "notify_channel_id", "message_id", "created_at")

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "campaign",
        "nickname",
        "birth_year",
        "bust_size",
        "attractiveness",
        "status",
        "reporter",
        "created_at",
    )

    list_filter = (
        "status",
        "campaign",
        "birth_year",
        "created_at",
    )

    search_fields = (
        "nickname",
        "birth_year",
        "bust_size",
        "bust_info",
        "attractiveness",
        "extra_info",
        "reporter__telegram_id",
    )

    readonly_fields = (
        "created_at",
        "reviewed_at",
        "reporter",
    )

