from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class CarouselButton(models.Model):
    """文字或回調按鈕（可選）"""
    BUTTON_TYPE_CHOICES = [
        ("url", "URL 按鈕"),
        ("callback", "回調按鈕"),
    ]
    text = models.CharField(_("按鈕文字"), max_length=50)
    type = models.CharField(_("類型"), max_length=20, choices=BUTTON_TYPE_CHOICES, default="url")
    url = models.URLField(_("按鈕連結"), blank=True, null=True)
    callback_data = models.CharField(_("回調數據"), max_length=100, blank=True, null=True)

    def __str__(self):
        return self.text


class CarouselConfig(models.Model):
    """輪播配置（Admin 動態管理）"""
    name = models.CharField(_("輪播名稱"), max_length=100)
    chat_id = models.BigIntegerField(_("群聊/頻道 ID"))
    message_text = models.TextField(_("輪播文字"), blank=True, default="")

    # 供擴展靜態按鈕（非翻頁）
    buttons = models.ManyToManyField(CarouselButton, blank=True, verbose_name=_("文字按鈕"))

    interval = models.IntegerField(_("輪播間隔（分鐘）"), default=30)
    page_size = models.IntegerField(_("每頁數量"), default=5)
    delete_previous = models.BooleanField(_("刪除上一條"), default=False)
    is_active = models.BooleanField(_("是否啟用"), default=True)
    is_pinned = models.BooleanField(_("是否置頂"), default=False)

    last_message_id = models.BigIntegerField(_("上一條消息 ID"), null=True, blank=True)
    last_sent_at = models.DateTimeField(_("上次發送時間"), null=True, blank=True)
    total_sent_count = models.IntegerField(_("總發送次數"), default=0)
    updated_at = models.DateTimeField(_("更新時間"), auto_now=True)

    # 用於回調前綴與唯一識別
    function_name = models.CharField(_("函數標識"), max_length=50, unique=True)
    # 從字符串路徑動態加載：如 'tgusers.tasks.fetch_merchants_task'
    data_fetcher = models.CharField(_("數據獲取函數"), max_length=200,
                                    help_text="函數路徑，如 'myapp.tasks.fetch_articles'")

    class Meta:
        verbose_name = _("輪播配置")
        verbose_name_plural = _("輪播配置")

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.interval < 5:
            raise ValidationError(_("輪播間隔不能小於 5 分鐘"))
        if not self.function_name:
            raise ValidationError(_("函數標識不可為空"))
        if not self.data_fetcher:
            raise ValidationError(_("數據獲取函數路徑不可為空"))

    def get_next_send_time(self):
        if self.last_sent_at:
            return self.last_sent_at + timezone.timedelta(minutes=self.interval)
        # 首次：延遲 1 分鐘啟動，避免保存抖動
        return timezone.now() + timezone.timedelta(minutes=1)

    def get_task_name_prefix(self):
        return f"carousel_function_{self.id}"

    def get_full_callback_prefix(self):
        # 統一格式：tgfunc_carousel_{function_name}_
        return f"tgfunccarousel_{self.function_name}_"

    def get_data_fetcher(self):
        """動態導入函數（字符串路徑）"""
        from django.utils.module_loading import import_string
        func = import_string(self.data_fetcher)
        return func

# Create your models here.
