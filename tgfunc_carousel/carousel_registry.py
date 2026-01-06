import logging
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler
from .models import CarouselConfig
from .carousel_bot import carousel_bot

logger = logging.getLogger(__name__)


class CarouselRegistry:
    """统一处理所有轮播回调：tgfunc_carousel_{function_name}_{action}_{page}"""

    def __init__(self):
        self.logger = logger

    def handle_all_callbacks(self, update: Update, context: CallbackContext):
        query = update.callback_query
        callback_data = query.data

        if not callback_data.startswith('tgfunccarousel_'):
            return

        try:
            parts = callback_data.split('_')
            print("解析", callback_data, parts)
            if len(parts) < 4:
                query.answer("回调格式错误", show_alert=True)
                return

            function_name = parts[1]
            action = parts[2]
            try:
                current_page = int(parts[3])
            except ValueError:
                query.answer("页码错误", show_alert=True)
                return

            config = self._get_carousel_config(function_name)
            if not config:
                query.answer("轮播配置不存在", show_alert=True)
                return

            if action == 'prev':
                target_page = max(1, current_page - 1)
                success = self._jump_to_page(config, query, target_page)
                query.answer("" if success else "已是第一页", show_alert=not success)

            elif action == 'next':
                target_page = current_page + 1
                success = self._jump_to_page(config, query, target_page)
                query.answer("" if success else "已是最后一页", show_alert=not success)

            elif action == 'indicator':
                query.answer(f"目前第 {current_page} 页")

            else:
                query.answer("未知操作", show_alert=True)

        except Exception as e:
            self.logger.error(f"[轮播回调] 处理失败 {callback_data}: {e}")
            query.answer("系统错误，请稍后重试", show_alert=True)

    def _get_carousel_config(self, function_name: str):
        try:
            return CarouselConfig.objects.get(function_name=function_name, is_active=True)
        except CarouselConfig.DoesNotExist:
            return None

    def _jump_to_page(self, config: CarouselConfig, query, target_page: int):
        try:
            return carousel_bot.jump_to_page(config, query, target_page)
        except Exception as e:
            self.logger.error(f"[轮播回调] 跳转失败 {config.function_name} → 第 {target_page} 页: {e}")
            return False

    def register_handlers(self, dispatcher):
        dispatcher.add_handler(CallbackQueryHandler(
            self.handle_all_callbacks,
            pattern=r"^tgfunccarousel_"
        ))


# 全局实例
registry = CarouselRegistry()
