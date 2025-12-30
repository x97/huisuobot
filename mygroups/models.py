# mygroups/models.py

from django.db import models


class MyGroup(models.Model):
    """允许机器人使用的群组及其关联频道"""
    group_name = models.CharField(max_length=255, null=True, blank=True, help_text="群组名称")
    group_chat_id = models.BigIntegerField(unique=True, db_index=True, help_text="群组 chat_id")
    group_username = models.CharField(max_length=255, null=True, blank=True, help_text="群组 @username")

    main_channel_id = models.BigIntegerField(null=True, blank=True, help_text="主频道 chat_id")
    report_channel_id = models.BigIntegerField(null=True, blank=True, help_text="报告频道 chat_id")
    notify_channel_id = models.BigIntegerField(null=True, blank=True, help_text="通知频道 chat_id")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MyGroup {self.group_chat_id}"
