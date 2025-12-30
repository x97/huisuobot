from .user_activity import register_user_activity
from .common import pre_process_user
from .group_guard import register_group_guard
from .back_to_main import register_back_to_main
from .start import register_start_handlers
from reports.handlers import register_report_handlers
from collect.handlers import (register_exchange_handlers, register_admin_appeal_handlers,
                              register_history_appeal_handlers)
from collect.handlers import (register_reward_manage_handlers, register_reward_publish_handlers,
                              register_reward_review_handlers, register_reward_submit_handlers,
                              register_reward_user_handlers, register_admin_add_staff_handlers)
from tgusers.handlers import (register_user_profile_handlers, register_adjust_handlers,
                              register_inheritance_handlers, register_inheritance_menu_handlers)
from collect.handlers.query_staff import register_query_staff_handlers
from interactions.handlers import register_interaction_handlers
from mall.handlers import register_all_mall_handers
from lottery.handlers import register_all_lottery_handlers
from telegram.ext import MessageHandler, Filters


def register_handlers(dp):
    # 全局用户更新（最优先）
    dp.add_handler(MessageHandler(Filters.all, pre_process_user), group=-1)
    #返回主菜单
    register_back_to_main(dp)
    # 用户提交悬赏
    register_reward_submit_handlers(dp)

    #用户继承
    register_inheritance_handlers(dp)
    register_inheritance_menu_handlers(dp)

    register_inheritance_handlers(dp)
    #机器人防拉保护
    register_group_guard(dp)

    #报告
    register_report_handlers(dp)
    # 兑换名片
    register_exchange_handlers(dp)
    # 管理员处理兑换名片申诉
    register_admin_appeal_handlers(dp)
    # 历史兑换名片信息
    register_history_appeal_handlers(dp)
    # 管理员管理悬赏任务
    register_reward_manage_handlers(dp)
    #发布悬赏
    register_reward_publish_handlers(dp)



    # 管理员审核悬赏
    register_reward_review_handlers(dp)

    #用户查看提交记录
    register_reward_user_handlers(dp)

    #用户查看自己信息
    register_user_profile_handlers(dp)


    #管理员调整用户积分/金币
    register_adjust_handlers(dp)


    #注册积分/金币商城
    register_all_mall_handers(dp)

    # 管理员手动添加技师信息
    register_admin_add_staff_handlers(dp)


    #注册抽奖相关
    register_all_lottery_handlers(dp)

    # 模糊查询技师信息
    register_query_staff_handlers(dp)
    register_interaction_handlers(dp)

    #开始菜单
    register_start_handlers(dp)

    #注册用户群聊发言处理
    register_user_activity(dp)
    # 用户发言监听 放在最后面
