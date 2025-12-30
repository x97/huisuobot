# common/message_utils/tasks.py
import logging
from typing import Optional, Union

from telegram import Message, TelegramError
from django_q.tasks import async_task, fetch
from typing import Union, Optional, Dict

logger = logging.getLogger(__name__)


def queue_message(
    chat_id: Union[int, str],
    text: str,
    buttons: Optional[list] = None,  # 保留button参数
    disable_web_page_preview: bool = True,
    pin_message: bool = False,
    parse_mode: str = 'HTML'
) -> str:
    """
    异步发送消息（支持button，彻底解决pickle序列化问题）
    :param buttons: 按钮字典，示例：{"按钮1": "callback_data_1", "按钮2": "callback_data_2"}
    """
    try:
        # 提交异步任务（仅传递可序列化参数）
        task_id = async_task(
            # 替换为你实际的函数导入路径
            'utils.message_utils.sender.send_text_message_cli',
            chat_id,
            text,
            buttons,                # 保留button参数（dict类型）
            disable_web_page_preview,
            pin_message,
            parse_mode,
            hook='utils.message_utils.tasks.message_hook',  # 替换为实际hook路径
            timeout=60,
            q_options={
                'queue': 'telegram_messages',
                'max_attempts': 3,    # 最多重试3次
                'ack_failures': True, # 标记失败任务，不再重复
                'retry_delay': 5      # 重试间隔5秒
            }
        )
        logger.info(f"消息任务提交成功 | task_id={task_id} | chat_id={chat_id} | button数量={len(buttons) if buttons else 0}")
        return task_id
    except Exception as e:
        logger.error(f"提交消息任务失败 | chat_id={chat_id} | 错误={str(e)}", exc_info=True)
        return ""




def message_hook(task):
    """
    任务回调函数（适配button参数）
    """
    try:
        # 安全获取参数
        chat_id = task.args[0] if (task.args and len(task.args) >= 1) else "未知"
        text_preview = ""
        button_count = 0
        if task.args and len(task.args) >= 2:
            text = task.args[1]
            text_preview = text[:50] + "..." if len(text) > 50 else text
        if task.args and len(task.args) >= 3 and task.args[2]:
            button_count = len(task.args[2])  # 统计按钮数量

        if task.success:
            result = task.result
            if result.get("success"):
                logger.info(
                    f"✅ 消息发送成功 | chat_id={chat_id} | message_id={result['message_id']} | "
                    f"文本预览={text_preview} | 按钮数量={button_count}"
                )
            else:
                logger.warning(
                    f"⚠️ 脚本执行失败 | chat_id={chat_id} | 文本预览={text_preview} | "
                    f"按钮数量={button_count} | 错误={result['error']}"
                )
        else:
            logger.error(
                f"❌ 任务执行失败 | chat_id={chat_id} | 文本预览={text_preview} | "
                f"按钮数量={button_count} | 错误={task.result}"
            )
    except Exception as e:
        logger.error(f"📌 回调函数执行异常 | 错误={str(e)}", exc_info=True)



def get_message_task_result(task_id: str) -> Optional[Message]:
    """
    根据任务ID查询异步任务结果（获取 send_text_message 返回的 Message 对象）
    :param task_id: queue_message 返回的任务ID
    :return: Message 对象（成功）/None（失败/未完成）
    """
    task = fetch(task_id)  # 根据ID获取任务对象
    if not task:
        logger.error(f"未找到任务：task_id={task_id}")
        return None

    if not task.success:
        logger.error(f"任务执行失败：task_id={task_id}，错误={task.result}")
        return None

    # task.result 就是 send_text_message 的返回值
    msg: Optional[Message] = task.result
    return msg
