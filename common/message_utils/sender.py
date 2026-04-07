import requests
import logging
from django.conf import settings
from celery import shared_task


logger = logging.getLogger(__name__)

@shared_task
def send_telegram_message(
    chat_id: int | str,
    text: str,
    buttons=None,
    parse_mode="HTML",
    disable_web_page_preview=True,
    pin_message=False,
):
    """1）格式 1：字典格式（最简单）
    buttons = {
    "按钮文字1": "callback_data_1",
    "按钮文字2": "callback_data_2",
    }
    2）格式 2：二维列表格式（自由排版）
    buttons = [
        [{"text": "按钮1", "callback_data": "data1"}],
        [{"text": "按钮2", "callback_data": "data2"}, {"text": "按钮3", "callback_data": "data3"}],
    ]

    """
    token = settings.TELEGRAM_BOT_TOKEN
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    # 自动支持按钮（兼容你原来的格式）
    if buttons:
        if isinstance(buttons, dict):
            keyboard = [[{"text": k, "callback_data": v} for k, v in buttons.items()]]
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        elif isinstance(buttons, list):
            payload["reply_markup"] = {"inline_keyboard": buttons}

    try:
        res = requests.post(api_url, json=payload, timeout=15).json()

        # 置顶消息
        if pin_message and res.get("ok"):
            msg_id = res["result"]["message_id"]
            pin_url = f"https://api.telegram.org/bot{token}/pinChatMessage"
            requests.post(pin_url, json={"chat_id": chat_id, "message_id": msg_id}, timeout=5)

    except Exception:
        pass
