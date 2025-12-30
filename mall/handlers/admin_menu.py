# mall/handlers/admin_menu.py
from telegram import Update
from telegram.ext import CallbackContext
from mall.keyboards import admin_mall_manager_main_menu
from telegram.ext import CallbackQueryHandler

def show_admin_mall_menu(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    current_text = q.message.text
    new_text = "请选择商城管理操作："
    if current_text != new_text:
        q.edit_message_text(new_text, reply_markup=admin_mall_manager_main_menu())
    else:
        # 如果内容一样，可以选择只更新按钮，或者直接忽略
        q.edit_message_reply_markup(reply_markup=admin_mall_manager_main_menu())

def register_show_admin_mall_menu(dispatcher):
    dispatcher.add_handler(CallbackQueryHandler(show_admin_mall_menu, pattern=r"^mall_admin:menu$"))
