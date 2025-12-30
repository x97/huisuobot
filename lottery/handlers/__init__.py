# lottery/handlers/__init__.py

from .admin_create import register_admin_create_handlers
from .admin_manage import register_admin_manage_handlers
from .user_join import register_user_join_handlers
from .user_wins import register_user_wins_handlers
from .lottery_menu import register_lottery_menu_handlers

def register_all_lottery_handlers(dp):
    register_admin_create_handlers(dp)
    register_admin_manage_handlers(dp)
    register_user_join_handlers(dp)
    register_user_wins_handlers(dp)
    register_lottery_menu_handlers(dp)

