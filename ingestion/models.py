from django.db import models
from django.utils import timezone


class IngestionSource(models.Model):
    """
    数据抓取来源（Telegram 频道 / 群组 / 用户 / 外部 API / 未来扩展）
    """

    PLATFORM_TYPES = (
        ("telegram", "Telegram"),
        ("xhs", "小红书"),
        ("douyin", "抖音"),
        ("api", "外部 API"),
    )

    SOURCE_TYPES = (
        ("telegram_channel", "Telegram 频道"),
        ("telegram_group", "Telegram 群组"),
        ("telegram_user", "Telegram 用户"),
        ("external_api", "外部 API"),
    )

    DATA_TYPES = (
        ("media", "媒体文件"),
        ("comment", "评论"),
        ("post", "帖子"),
        ("tguser", "用户数据"),
        ("post_tguser", "帖子 + 用户"),
    )

    FETCH_MODES = (
        ("forward", "从最新往前抓（增量抓取）"),
        ("backward", "从最旧往后抓（补档）"),
    )

    # 平台
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_TYPES,
        default="telegram",
        help_text="数据来源平台"
    )

    # 来源类型
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)

    # Telegram 相关字段
    channel_id = models.BigIntegerField(null=True, blank=True, help_text="频道/群组 ID")
    channel_username = models.CharField(max_length=255, null=True, blank=True, help_text="@username")
    channel_name = models.CharField(max_length=255, null=True, blank=True, help_text="频道名称")

    # 抓取配置
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default="post")
    fetch_mode = models.CharField(max_length=20, choices=FETCH_MODES, default="forward")
    is_active = models.BooleanField(default=True, help_text="是否启用抓取")

    # 抓取进度
    last_message_id = models.BigIntegerField(null=True, blank=True, help_text="上次抓取的 message_id")
    last_fetched_at = models.DateTimeField(null=True, blank=True, help_text="上次抓取时间")

    # 扩展配置
    extra_config = models.JSONField(null=True, blank=True, help_text="额外配置，如过滤规则、解析规则等")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.platform}] {self.channel_name or self.channel_username or self.channel_id}"
