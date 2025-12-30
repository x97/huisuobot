#common/broadcast.py
# 导入模型
import logging
from typing import List, Tuple, Union
from typing import Optional
from telegram import Update

from common.message_utils import queue_message  # 你的异步发送函数

logger = logging.getLogger(__name__)


# ---------------------- 广播函数 ----------------------
def send_broadcast_to_users(
        user_ids: List[Union[int, str]],
        text: str,
        buttons: Optional[list] = None,
        disable_web_page_preview: bool = False,
        pin_message: bool = False,
        parse_mode: str = 'HTML'
) -> Tuple[int, int, List[str]]:
    if not isinstance(user_ids, list) or len(user_ids) == 0:
        logger.warning("用户ID列表为空或格式错误，无需发送")
        return (0, 0, [])

    valid_user_ids = []
    seen = set()
    for uid in user_ids:
        if uid and (isinstance(uid, int) or (isinstance(uid, str) and uid.strip())):
            uid_str = str(uid).strip()
            if uid_str not in seen:
                seen.add(uid_str)
                valid_user_ids.append(uid_str)

    total_users = len(valid_user_ids)
    task_ids = []
    successfully_submitted = 0

    for user_id in valid_user_ids:
        try:
            task_id = queue_message(
                chat_id=user_id,
                text=text,
                buttons=buttons,
                disable_web_page_preview=disable_web_page_preview,
                pin_message=pin_message,
                parse_mode=parse_mode
            )
            task_ids.append(task_id)
            successfully_submitted += 1
            logger.info(f"✅ 已提交发送任务：user_id={user_id} task_id={task_id}")
        except Exception as e:
            logger.error(f"❌ 提交发送任务失败：user_id={user_id} 错误：{e}", exc_info=True)

    logger.info(f"消息广播任务提交完成。成功提交：{successfully_submitted}/{total_users}")
    return (successfully_submitted, total_users, task_ids)