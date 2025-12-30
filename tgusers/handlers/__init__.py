from .profile import register_user_profile_handlers
from .adjust import register_adjust_handlers
from .menu import register_inheritance_menu_handlers
from .inheritance import register_inheritance_handlers

def register_all_user_handlers(dispatcher):
    register_user_profile_handlers(dispatcher)
    register_adjust_handlers(dispatcher)
    register_inheritance_menu_handlers(dispatcher)
    register_inheritance_handlers(dispatcher)