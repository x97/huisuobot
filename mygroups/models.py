# mygroups/models.py

from django.db import models


class MyGroup(models.Model):
    """允许机器人使用的群组及其关联频道"""
    group_name = models.CharField(max_length=255, null=True, blank=True, help_text="群组名称")
    group_chat_id = models.BigIntegerField(unique=True, db_index=True, help_text="群组 chat_id")
    group_username = models.CharField(max_length=255, null=True, blank=True, help_text="群组 @username")

    main_channel_id = models.BigIntegerField(null=True, blank=True, help_text="主频道 chat_id")
    main_channel_username = models.CharField(max_length=255, null=True, blank=True,
                                             help_text="主频道 @username")

    report_channel_id = models.BigIntegerField(null=True, blank=True, help_text="报告频道 chat_id")
    report_channel_username = models.CharField(max_length=255, null=True, blank=True,
                                             help_text="报告频道 @username")

    notify_channel_id = models.BigIntegerField(null=True, blank=True, help_text="通知频道 chat_id")
    notify_channel_username = models.CharField(max_length=255, null=True, blank=True,
                                             help_text="通知频道 @username")
    # ✅ 新增：频道绑定的讨论组（评论必须发这里）
    notify_discuss_group_id = models.BigIntegerField(null=True, blank=True, help_text="频道的讨论组")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MyGroup {self.group_chat_id}"


    @classmethod
    def ALLOWED_GROUP_IDS(cls):
        all_ids = cls.get_all_ids()
        result = []

        result.extend(all_ids['group_ids'])
        result.extend(all_ids['channel_ids'])
        result.extend(all_ids['report_channel_ids'])
        return result
