import requests
import logging
from django.conf import settings
logger = logging.getLogger(__name__)

# ========================
# 同步版本：直接发送，不进 celery
# ========================
def send_telegram_message_sync(
    chat_id: int | str,
    text: str,
    buttons=None,
    parse_mode="HTML",
    disable_web_page_preview=True,
    pin_message=False,
):
    """
    同步发送 Telegram 消息
    兼容按钮格式：dict / 二维列表
    """
    token = settings.TELEGRAM_BOT_TOKEN
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    # 按钮兼容处理
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
            requests.post(pin_url, json={
                "chat_id": chat_id,
                "message_id": msg_id
            }, timeout=5)

        # 返回消息体（方便获取 message_id）
        return res

    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        return None

def delete_telegram_message_sync(chat_id: int | str, message_id: int):
    """同步删除 Telegram 消息"""
    try:
        token = settings.TELEGRAM_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/deleteMessage"
        requests.post(url, json={
            "chat_id": chat_id,
            "message_id": message_id
        }, timeout=5)
    except Exception:
        pass


# ========================
# 你的原有 celery 异步任务（调用同步函数）
# ========================
from celery import shared_task

@shared_task
def send_telegram_message(
    chat_id: int | str,
    text: str,
    buttons=None,
    parse_mode="HTML",
    disable_web_page_preview=True,
    pin_message=False,
):
    send_telegram_message_sync(
        chat_id=chat_id,
        text=text,
        buttons=buttons,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
        pin_message=pin_message
    )
