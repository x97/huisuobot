# common/message_utils/sender.py
import sys
import json
import logging
import subprocess
from typing import Union, Optional, Dict
from django_q.tasks import async_task
from django.conf import settings

logger = logging.getLogger(__name__)



def send_text_message_cli(
    chat_id: Union[int, str],
    text: str,
    buttons:Optional[list] = None,
    disable_web_page_preview: bool = False,
    pin_message: bool = False,
    parse_mode: str = 'HTML'
) -> dict:
    """
    调用Django Command发送消息（过滤非JSON内容）
    """
    cmd_args = [
        'manage.py',
        'send_telegram_msg',
        str(chat_id),
        text,
        '--parse-mode', parse_mode,
        '--disable-web-page-preview', 'True' if disable_web_page_preview else 'False'
    ]

    if pin_message:
        cmd_args.extend(['--pin-message', 'True'])
    if buttons:
        buttons_json = json.dumps(buttons, ensure_ascii=False)
        cmd_args.extend(['--buttons', buttons_json])

    cmd = [sys.executable] + cmd_args
    project_root = settings.BASE_DIR

    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=60
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # ========== 核心：提取最后一行的JSON ==========
        # 分割所有行，只取最后一行（Command最后只输出一行JSON）
        stdout_lines = stdout.split('\n')
        json_line = ""
        for line in reversed(stdout_lines):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):  # 判定为JSON对象
                json_line = line
                break

        # 解析JSON
        if json_line:
            return json.loads(json_line)
        else:
            # 无有效JSON行，但返回码0 → 判定成功
            if result.returncode == 0:
                logger.warning(f"未找到JSON，但Command执行成功 | chat_id={chat_id} | stdout={stdout[:200]}")
                return {
                    "success": True,
                    "error": "未解析到JSON，但消息发送成功",
                    "message_id": None,
                    "chat_id": chat_id
                }
            else:
                error_msg = stderr or f"Command执行失败，返回码：{result.returncode}"
                return {"success": False, "error": error_msg}

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败 | chat_id={chat_id} | json_line={json_line[:100]} | error={str(e)}")
        if result.returncode == 0:
            return {
                "success": True,
                "error": f"JSON解析失败，但消息发送成功：{str(e)}",
                "message_id": None,
                "chat_id": chat_id
            }
        else:
            return {"success": False, "error": f"JSON解析失败+Command执行失败：{str(e)}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "发送超时（60秒）"}
    except Exception as e:
        return {"success": False, "error": f"发送异常：{str(e)}"}
