import logging
from django.conf import settings
from telegram import Bot
from telegram.error import TelegramError
from .models import CarouselConfig
from .generic_carousel_manager import GenericCarouselManager

logger = logging.getLogger(__name__)


class CarouselBot:
    """轮播机器人：同时提供同步和异步接口"""

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.bot = Bot(token=self.bot_token)
        self.manager = GenericCarouselManager(self.bot_token)

    # 同步版本：给 Django-Q 调度用
    #其实是再次发送
    def send_carousel_message_sync(self, config: CarouselConfig):
        try:
            data_fetcher = config.get_data_fetcher()

            # 如果需要删除上一条
            if config.delete_previous and config.last_message_id:
                try:
                    self.bot.delete_message(chat_id=config.chat_id, message_id=config.last_message_id)
                    logger.info(f"[轮播机器人] 已删除上一条消息 {config.last_message_id}")
                except TelegramError as e:
                    logger.warning(f"[轮播机器人] 删除上一条失败: {e}")


            text, total_pages = data_fetcher(1, config.page_size, config=config)
            keyboard = self.manager.create_carousel(
                chat_id=config.chat_id,
                data_fetcher=data_fetcher,
                callback_prefix=config.get_full_callback_prefix(),
                interval_seconds=config.interval * 60,
                delete_previous=config.delete_previous,
                page_size=config.page_size,
                last_message_id=config.last_message_id,
            )._build_keyboard(total_pages, 1)

            msg = self.bot.send_message(
                chat_id=config.chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            # 更新 last_message_id
            config.last_message_id = msg.message_id
            config.save(update_fields=["last_message_id"])

            message_id = msg.message_id
            if config.is_pinned and message_id:
                try:
                    self.bot.pin_chat_message(chat_id=config.chat_id, message_id=message_id)
                except TelegramError as e:
                    logger.warning(f"[轮播机器人] 置顶失败: {e}")
            return True, message_id
        except Exception as e:
            logger.error(f"[轮播机器人] 同步发送失败（{config.name}）: {e}")
            return False, None

    # 异步版本：给 Bot handler 用
    async def send_carousel_message(self, config: CarouselConfig):
        try:
            data_fetcher = config.get_data_fetcher()
            carousel = self.manager.create_carousel(
                chat_id=config.chat_id,
                data_fetcher=data_fetcher,
                callback_prefix=config.get_full_callback_prefix(),
                interval_seconds=config.interval * 60,
                delete_previous=config.delete_previous,
                page_size=config.page_size,
                last_message_id=config.last_message_id,
            )
            await carousel.send_carousel(config)
            message_id = carousel.current_message_id
            if config.is_pinned and message_id:
                await self.pin_message(config.chat_id, message_id)
            return True, message_id
        except Exception as e:
            logger.error(f"[轮播机器人] 异步发送失败（{config.name}）: {e}")
            return False, None


    async def jump_to_page_sync(self, config: CarouselConfig, query,target_page: int):
        """同步版本，给 v13.7 的 CallbackQueryHandler 用"""
        try:
            data_fetcher = config.get_data_fetcher()
            carousel = self.manager.create_carousel(
                chat_id=config.chat_id,
                data_fetcher=data_fetcher,
                callback_prefix=config.get_full_callback_prefix(),
                interval_seconds=config.interval * 60,
                delete_previous=config.delete_previous,
                page_size=config.page_size,
                last_message_id=config.last_message_id,
            )
            # 注意：这里直接调用同步方法，不要用 await
            success = await carousel.jump_to_page(config, query,target_page)
            return success
        except Exception as e:
            logger.error(f"[轮播机器人] 跳转失败（{config.function_name} → 第 {target_page} 页）: {e}")
            return False

    def jump_to_page(self, config: CarouselConfig, query, target_page: int):
        """同步版本，给 v13.7 的 CallbackQueryHandler 用"""
        try:
            data_fetcher = config.get_data_fetcher()
            carousel = self.manager.create_carousel(
                chat_id=config.chat_id,
                data_fetcher=data_fetcher,
                callback_prefix=config.get_full_callback_prefix(),
                interval_seconds=config.interval * 60,
                delete_previous=config.delete_previous,
                page_size=config.page_size,
                last_message_id=config.last_message_id
            )
            success = carousel.jump_to_page(config, query, target_page)
            return success
        except Exception as e:
            logger.error(f"[轮播机器人] 跳转失败（{config.function_name} → 第 {target_page} 页）: {e}")
            return False

    async def pin_message(self, chat_id: int, message_id: int):
        try:
            await self.bot.pin_chat_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"[轮播机器人] 已置顶消息 {message_id} 至 {chat_id}")
            return True
        except TelegramError as e:
            logger.warning(f"[轮播机器人] 置顶失败: {e}")
            return False


# 全局实例
carousel_bot = CarouselBot()
