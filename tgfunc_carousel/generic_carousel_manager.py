import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.error import TelegramError
from tgfunc_carousel.models import CarouselConfig


logger = logging.getLogger(__name__)


class GenericCarouselManager:
    """輪播管理器：負責創建 CarouselInstance"""

    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)

    def create_carousel(self, chat_id, data_fetcher, callback_prefix,
                        interval_seconds, delete_previous, page_size,last_message_id):
        return CarouselInstance(
            bot=self.bot,
            chat_id=chat_id,
            data_fetcher=data_fetcher,  # (page, page_size) -> (text, total_pages)
            callback_prefix=callback_prefix,
            delete_previous=delete_previous,
            page_size=page_size,
            last_message_id=last_message_id,
        )

class CarouselInstance:
    """單個輪播實例：發送與翻頁"""

    def __init__(self, bot: Bot, chat_id: int, data_fetcher, callback_prefix: str,
                 delete_previous: bool, page_size: int, last_message_id: int ):
        self.bot = bot
        self.chat_id = chat_id
        self.data_fetcher = data_fetcher
        self.callback_prefix = callback_prefix
        self.delete_previous = delete_previous
        self.page_size = page_size
        self.current_page = 1
        self.current_message_id = None
        self.last_message_id = last_message_id

    async def send_carousel(self, config:CarouselConfig):
        """首次發送輪播消息"""
        try:
            text, total_pages = self.data_fetcher(self.current_page, self.page_size, config=config)
            keyboard = self._build_keyboard(total_pages, self.current_page)

            msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
                disable_web_page_preview = True
            )
            self.current_message_id = msg.message_id
            self.last_message_id = msg.message_id  #首次发送消息记录上次id==这次id
            config.last_message_id = msg.message_id
            config.save(update_fields=["last_message_id"])

            logger.info(f"[Carousel] 已發送消息 {self.current_message_id} 至 {self.chat_id}")
        except TelegramError as e:
            logger.error(f"[Carousel] 發送失敗: {e}")
            raise

    def jump_to_page(self, config: CarouselConfig, query, target_page: int):
        """
        跳轉到指定頁面，使用 query.edit_message_text
        注意：這裡必須傳入 update.callback_query
        """
        try:
            text, total_pages = self.data_fetcher(target_page, self.page_size, config=config)
            if target_page < 1 or target_page > total_pages:
                return False

            keyboard = self._build_keyboard(total_pages, target_page)
            query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
                disable_web_page_preview = True,
            )
            self.current_page = target_page
            logger.info(f"[Carousel] 已跳轉至第 {target_page} 頁")
            return True
        except TelegramError as e:
            logger.error(f"[Carousel] 跳轉失敗: {e}")
            return False

    def _build_keyboard(self, total_pages: int, current_page: int):
        """生成翻頁按鈕：tgfunc_carousel_{function_name}_{action}_{page}"""
        buttons = []
        if current_page > 1:
            buttons.append(
                InlineKeyboardButton("⬅️ 上一頁",
                                     callback_data=f"{self.callback_prefix}prev_{current_page}")
            )
        buttons.append(
            InlineKeyboardButton(f"第 {current_page}/{total_pages} 頁",
                                 callback_data=f"{self.callback_prefix}indicator_{current_page}")
        )
        if current_page < total_pages:
            buttons.append(
                InlineKeyboardButton("下一頁 ➡️",
                                     callback_data=f"{self.callback_prefix}next_{current_page}")
            )
        return InlineKeyboardMarkup([buttons])
