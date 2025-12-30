# telethon_account/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class TelethonAccount(models.Model):
    """
    存储 Telethon 账号信息和会话的模型。
    """
    STATUS_CHOICES = (
        ('idle', _('Idle')),
        ('logging_in', _('Logging in')),
        ('authorized', _('Authorized')),
        ('banned', _('Banned')),
        ('limited', _('Limited')),
        ('error', _('Error')),
    )

    api_id = models.IntegerField(_('API ID'))
    api_hash = models.CharField(_('API Hash'), max_length=64)
    phone_number = models.CharField(_('Phone Number'), max_length=20, unique=True)
    session_string = models.TextField(_('Session String'), blank=True,  null=True,
                                      help_text=_('Telethon 会话的字符串表示，用于免密码登录。'))

    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='idle')
    # 记录受限时间，用于在命令行登录时跳过
    limited_until = models.DateTimeField(_('Limited Until'), null=True, blank=True,
                                         help_text=_('账号被限制操作的时间，在此之前不会被选为执行任务的账号。'))
    error_message = models.TextField(_('Last Error Message'), blank=True)
    is_active = models.BooleanField(_("是否有效"), default=True)
    request_count =  models.IntegerField(_('Request Count'), default=0)
    last_used = models.DateTimeField(_('Created At'), auto_now_add=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_telethon_accounts',
        verbose_name=_('Created By')
    )

    def __str__(self):
        return f"{self.phone_number} ({self.get_status_display()})"

    class Meta:
        verbose_name = _('Telethon Account')
        verbose_name_plural = _('Telethon Accounts')
        ordering = ['-updated_at']

    @property
    def is_authorized(self):
        return self.status == 'authorized'

    @property
    def is_limited(self):
        import datetime
        return self.status == 'limited' and self.limited_until and self.limited_until > datetime.datetime.now(
            datetime.timezone.utc)
