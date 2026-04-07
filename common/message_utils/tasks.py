from celery import shared_task
import requests
from django.conf import settings
from .sender import send_telegram_message



def queue_message(
    chat_id,
    text,
    buttons=None,
    disable_web_page_preview=True,
    pin_message=False,
    parse_mode="HTML",
):
    # 直接调用 Celery delay
    send_telegram_message.delay(
        chat_id,
        text,
        buttons,
        parse_mode,
        disable_web_page_preview,
        pin_message,
    )
    return ""
