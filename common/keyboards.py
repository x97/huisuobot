# common/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .callbacks import make_cb

def single_button(label: str, prefix: str, action: str, *args) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=make_cb(prefix, action, *args))

def button_row(*buttons):
    return list(buttons)

def build_markup(rows):
    """
    rows: List[List[InlineKeyboardButton]]，主菜单用这个把多行合并成 InlineKeyboardMarkup
    """
    return InlineKeyboardMarkup(rows)

def row(*buttons):
    return list(buttons)

def append_back_button(keyboard=None, text="🔙 返回主菜单", callback_data=None, prefix="core", action="back_main"):
    if callback_data is None:
        callback_data = make_cb(prefix, action)
    if isinstance(keyboard, InlineKeyboardMarkup):
        keyboard = keyboard.inline_keyboard
    if keyboard is None:
        keyboard = []
    new_keyboard = list(keyboard)
    new_keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
    return InlineKeyboardMarkup(new_keyboard)
