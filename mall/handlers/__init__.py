from .admin_add_product import register_admin_add_product_handlers
from .admin_manage_products import register_admin_manage_handlers
from .admin_menu import register_show_admin_mall_menu
from .admin_verify_product import register_admin_verify_handlers
from .user_list_products import register_user_list_handlers
from .user_history import register_user_history_handlers
from .uesr_menu import register_show_user_mall_menu
from .user_redeem_product import register_user_redeem_handlers


def register_all_mall_handers(dispatcher):
    register_admin_add_product_handlers(dispatcher)
    register_admin_manage_handlers(dispatcher)
    register_show_admin_mall_menu(dispatcher)
    register_admin_verify_handlers(dispatcher)
    register_user_list_handlers(dispatcher)
    register_user_history_handlers(dispatcher)
    register_show_user_mall_menu(dispatcher)
    register_user_redeem_handlers(dispatcher)