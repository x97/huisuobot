# tgpoker_bot/management/commands/send_telegram_msg.py
import os
import sys
import json
import logging
from io import StringIO
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from telegram import Bot, TelegramError, InlineKeyboardMarkup, InlineKeyboardButton

# 配置日志到stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def build_keyboard(buttons_list: list) -> InlineKeyboardMarkup:
    """
    根据列表套字典的格式生成 Telegram 内联按钮
    :param buttons_list: 按钮配置列表，示例：[{"按钮文本1": "回调数据1"}, {"按钮文本2": "回调数据2"}]
    :return: InlineKeyboardMarkup 按钮布局对象
    """
    keyboard = []
    # 遍历列表中的每个字典元素
    for btn_dict in buttons_list:
        # 遍历字典的键值对（每个字典仅保留一组键值：文本->回调数据）
        for btn_text, callback_data in btn_dict.items():
            # 生成单个按钮，每行1个
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


class Command(BaseCommand):
    help = '给Telegram聊天/频道发送消息（纯JSON输出）'
    style = None  # 禁用样式输出

    def add_arguments(self, parser):
        parser.add_argument('chat_id', type=str, help='目标聊天ID/频道用户名')
        parser.add_argument('text', type=str, help='要发送的消息文本')
        parser.add_argument('--buttons', type=str, default=None)
        parser.add_argument('--parse-mode', type=str, default='HTML')
        parser.add_argument('--disable-web-page-preview',
                            type=lambda x: x.lower() in ('true', '1', 'yes'),
                            default=False)
        parser.add_argument('--pin-message',
                            type=lambda x: x.lower() in ('true', '1', 'yes'),
                            default=False)

    def handle(self, *args, **options):
        # ========== 核心：临时重定向stdout到内存缓冲区 ==========
        original_stdout = sys.stdout
        sys.stdout = StringIO()  # 所有print/self.stdout.write都会到这里

        # 初始化结果
        result = {
            "success": False,
            "error": "",
            "message_id": None,
            "chat_id": options['chat_id']
        }

        try:
            # 1. 校验Token
            if not hasattr(settings, 'TELEGRAM_BOT_TOKEN') or not settings.TELEGRAM_BOT_TOKEN:
                raise CommandError("未配置TELEGRAM_BOT_TOKEN")

            # 2. 解析参数
            chat_id = options['chat_id']
            text = options['text']
            buttons_list = json.loads(options['buttons']) if options['buttons'] else None
            parse_mode = options['parse_mode']
            disable_web_page_preview = options['disable_web_page_preview']
            pin_message = options['pin_message']

            # 3. 转换chat_id类型
            try:
                chat_id = int(chat_id)
            except ValueError:
                pass

            # 4. 发送消息
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            reply_markup = build_keyboard(buttons_list) if buttons_list else None

            msg = bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )

            if pin_message:
                bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id)

            # 更新成功结果
            result["success"] = True
            result["message_id"] = msg.message_id
            logger.info(f"消息发送成功 | chat_id={chat_id} | message_id={msg.message_id}")

        except CommandError as e:
            result["error"] = str(e)
            logger.error(f"参数错误：{str(e)}")
        except TelegramError as e:
            result["error"] = str(e)
            logger.error(f"Telegram发送失败：{str(e)}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"未知错误：{str(e)}", exc_info=True)
        finally:
            # ========== 关键操作 ==========
            # 1. 恢复原始stdout
            sys.stdout = original_stdout
            # 2. 只输出纯JSON到stdout（无任何额外内容）
            print(json.dumps(result, ensure_ascii=False))
            # 3. 设置返回码
            sys.exit(0 if result["success"] else 1)
