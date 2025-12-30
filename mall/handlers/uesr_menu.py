# mall/handlers/user_menu.py
from telegram import Update
from telegram.ext import CallbackContext
from mall.keyboards import user_mall_manager_main_menu
from tgusers.services import update_or_create_user
from telegram.ext import CallbackQueryHandler

def show_user_mall_menu(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    user = update_or_create_user(update.effective_user)
    q.edit_message_text(
        f"🎯 积分商城\n你的积分：{user.points}\n你的金币：{user.coins}",
        reply_markup=user_mall_manager_main_menu(user)
    )
def register_show_user_mall_menu(dispatcher):
    dispatcher.add_handler(CallbackQueryHandler(show_user_mall_menu, pattern=r"^mall_user:menu$"))