"""主要做抽奖列表相关的handler"""
from datetime import timedelta  # 需要导入 timedelta

from django.utils import timezone
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler, CallbackContext
)

from .models import Lottery

# 抽奖列表相关状态
LOTTERY_LIST_MAIN, SHOW_ONGOING, SHOW_ENDED, CONFIRM_CANCEL = range(10, 14)

"""
抽奖列表主菜单（点击「抽奖列表」按钮触发）
"""

def show_lottery_list_main(update: Update, context: CallbackContext):
    """显示抽奖列表主菜单（正在进行/已结束）"""
    query = update.callback_query
    query.answer()

    # 结束所有对话
    from common.utils import end_all_conversations
    end_all_conversations(context)

    # 构建菜单
    keyboard = [
        [InlineKeyboardButton("🔄 正在进行", callback_data="lottery_ongoing")],
        [InlineKeyboardButton("📅 已结束（近1个月）", callback_data="lottery_ended")],
        [InlineKeyboardButton("🔙 返回抽奖管理", callback_data="lottery_management")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 更新消息
    query.edit_message_text(
        text="🎟️ 抽奖列表\n请选择查看类型：",
        reply_markup=reply_markup
    )
    return LOTTERY_LIST_MAIN

"""这个函数将接收抽奖列表和当前页码，返回要发送的文本和键盘布局。"""

def generate_lottery_list_message(lotteries, page, is_ongoing, total):
    """
    生成抽奖列表的消息文本和键盘布局
    :param lotteries: 当前页的抽奖 QuerySet
    :param page: 当前页码
    :param is_ongoing: 是否为“正在进行”的抽奖
    :param total: 总抽奖数
    :return: (text, reply_markup)
    """
    PAGE_SIZE = 5
    text_parts = []

    if is_ongoing:
        title = "🔄 正在进行的抽奖"
    else:
        title = "📅 已结束的抽奖（近1个月）"

    text_parts.append(f"{title}\n第 {page} 页 / 共 {((total + PAGE_SIZE - 1) // PAGE_SIZE)} 页\n")

    if not lotteries:
        text_parts.append("暂无抽奖记录。")
        keyboard = [[InlineKeyboardButton("🔙 返回列表菜单", callback_data="lottery_list_main")]]
    else:
        # 为每个抽奖生成一行文本和对应的按钮
        for idx, lottery in enumerate(lotteries, 1):
            status = "🔄 进行中" if is_ongoing else "✅ 已开奖"
            prize_info = lottery.prizes.first().name if lottery.prizes.exists() else "无"

            text_parts.append(
                f"{idx}. **{lottery.title}**\n"
                f"   📅 截止时间：{lottery.end_time.strftime('%Y-%m-%d %H:%M')}\n"
                f"   🏆 奖品：{prize_info}\n"
                f"   📝 状态：{status}\n"
            )

        # 构建键盘
        keyboard = []
        # 为每个抽奖添加“取消”按钮（仅正在进行的）
        for lottery in lotteries:
            if is_ongoing:
                cancel_callback = f"confirm_cancel_{lottery.id}"
                # 每个抽奖项的按钮行
                keyboard.append([
                    InlineKeyboardButton(f"🚫 取消[{lottery.title}]", callback_data=cancel_callback)
                ])

        # 分页控制按钮
        pagination_buttons = []
        if page > 1:
            prev_callback = f"lottery_prev_{'ongoing' if is_ongoing else 'ended'}_{page - 1}"
            pagination_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=prev_callback))

        if (page * PAGE_SIZE) < total:
            next_callback = f"lottery_next_{'ongoing' if is_ongoing else 'ended'}_{page + 1}"
            pagination_buttons.append(InlineKeyboardButton("➡️ 下一页", callback_data=next_callback))

        if pagination_buttons:
            keyboard.append(pagination_buttons)

        # 返回按钮
        keyboard.append([InlineKeyboardButton("🔙 返回列表菜单", callback_data="lottery_list_main")])

    return "".join(text_parts), InlineKeyboardMarkup(keyboard)


"""分页显示抽奖列表（核心逻辑）"""
def show_lottery_page(update: Update, context: CallbackContext, is_ongoing: bool, page: int = 1):
    """分页显示抽奖列表（支持正在进行/已结束）- 修正版"""
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    # 分页配置
    PAGE_SIZE = 5
    offset = (page - 1) * PAGE_SIZE

    # 查询条件
    if is_ongoing:
        lotteries = Lottery.objects.filter(
            is_active=True,
            is_drawn=False,
            end_time__gt=timezone.now()
        ).order_by('-created_at')
    else:
        one_month_ago = timezone.now() - timedelta(days=30)
        lotteries = Lottery.objects.filter(
            is_drawn=True,
            end_time__gte=one_month_ago
        ).order_by('-end_time')

    total = lotteries.count()
    current_lotteries = lotteries[offset:offset + PAGE_SIZE]

    # 调用辅助函数生成消息和键盘
    text, reply_markup = generate_lottery_list_message(current_lotteries, page, is_ongoing, total)

    # 更新消息
    try:
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        # 如果编辑失败（如消息已被删除），则发送新消息
        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # 保存当前状态
    context.user_data['current_lottery_page'] = page
    context.user_data['current_lottery_type'] = 'ongoing' if is_ongoing else 'ended'

"""正在进行 / 已结束抽奖的入口处理"""

def handle_ongoing_lotteries(update: Update, context: CallbackContext):
    """处理「正在进行」抽奖列表"""
    show_lottery_page(update, context, is_ongoing=True, page=1)
    return SHOW_ONGOING

def handle_ended_lotteries(update: Update, context: CallbackContext):
    """处理「已结束」抽奖列表"""
    show_lottery_page(update, context, is_ongoing=False, page=1)
    return SHOW_ENDED


"""分页切换逻辑（上一页 / 下一页）"""

def handle_lottery_pagination(update: Update, context: CallbackContext):
    """处理抽奖列表分页切换"""
    query = update.callback_query
    callback_data = query.data

    # 解析回调数据（格式：lottery_prev_ongoing_2 / lottery_next_ended_3）
    parts = callback_data.split('_')
    action = parts[1]  # prev/next
    lottery_type = parts[2]  # ongoing/ended
    page = int(parts[3])

    # 显示目标页
    is_ongoing = (lottery_type == 'ongoing')
    show_lottery_page(update, context, is_ongoing=is_ongoing, page=page)

    return SHOW_ONGOING if is_ongoing else SHOW_ENDED

"""取消抽奖功能（含定时任务停止）"""

def confirm_cancel_lottery(update: Update, context: CallbackContext):
    """确认取消抽奖（二次确认）"""
    query = update.callback_query
    query.answer()
    lottery_id = query.data.split('_')[-1]  # 从回调数据中获取抽奖ID

    # 保存抽奖ID到 context，供确认后使用
    context.user_data['cancel_lottery_id'] = lottery_id

    # 二次确认菜单
    keyboard = [
        [InlineKeyboardButton("✅ 确认取消", callback_data="do_cancel_lottery")],
        [InlineKeyboardButton("❌ 取消操作", callback_data="cancel_cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        text="⚠️ 确认取消抽奖？\n取消后将删除抽奖记录并停止开奖任务。",
        reply_markup=reply_markup
    )
    return CONFIRM_CANCEL

def do_cancel_lottery(update: Update, context: CallbackContext):
    """执行取消抽奖（删除记录 + 停止定时任务）"""
    from .draw import scheduler
    query = update.callback_query
    query.answer()
    lottery_id = context.user_data.get('cancel_lottery_id')

    if not lottery_id:
        query.edit_message_text(text="❌ 取消失败：未找到抽奖记录。")
        return LOTTERY_LIST_MAIN

    try:
        # 1. 查询抽奖（仅允许取消正在进行的）
        lottery = Lottery.objects.get(
            id=lottery_id,
            is_active=True,
            is_drawn=False,
            end_time__gt=timezone.now()
        )

        # 2. 停止定时任务（APScheduler）
        job_id = f"lottery_draw_{lottery.id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print(f"⏹️ 已停止定时任务：{job_id}")

        # 3. 删除抽奖记录（或标记为已取消，根据需求选择）
        lottery.delete()
        print(f"🗑️ 已删除抽奖：{lottery.title}（ID：{lottery.id}）")

        # 4. 反馈结果
        keyboard = [[InlineKeyboardButton("🔙 返回抽奖列表", callback_data="lottery_ongoing")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"✅ 抽奖《{lottery.title}》已成功取消！",
            reply_markup=reply_markup
        )

    except Lottery.DoesNotExist:
        query.edit_message_text(text="❌ 取消失败：抽奖已结束或不存在。")
    except Exception as e:
        query.edit_message_text(text=f"❌ 取消失败：{str(e)}")

    return LOTTERY_LIST_MAIN

def cancel_cancel(update: Update, context: CallbackContext):
    """取消取消操作（返回正在进行的抽奖列表）"""
    query = update.callback_query
    query.answer()

    show_lottery_page(update, context, is_ongoing=True, page=1)
    return SHOW_ONGOING


"""注册处理器（整合到现有逻辑）"""
def register_lottery_list_handlers(dp):
    """注册抽奖列表相关处理器"""
    # 1. 抽奖列表主菜单（从抽奖管理菜单进入）
    dp.add_handler(CallbackQueryHandler(
        show_lottery_list_main,
        pattern='^list_lotteries$'
    ))

    # 2. 正在进行/已结束抽奖入口
    dp.add_handler(CallbackQueryHandler(
        handle_ongoing_lotteries,
        pattern='^lottery_ongoing$'
    ))
    dp.add_handler(CallbackQueryHandler(
        handle_ended_lotteries,
        pattern='^lottery_ended$'
    ))

    # 3. 分页切换（上一页/下一页）
    dp.add_handler(CallbackQueryHandler(
        handle_lottery_pagination,
        pattern='^lottery_(prev|next)_(ongoing|ended)_\d+$'
    ))

    # 4. 取消抽奖（二次确认 + 执行）
    dp.add_handler(CallbackQueryHandler(
        confirm_cancel_lottery,
        pattern='^confirm_cancel_\d+$'
    ))
    dp.add_handler(CallbackQueryHandler(
        do_cancel_lottery,
        pattern='^do_cancel_lottery$'
    ))
    dp.add_handler(CallbackQueryHandler(
        cancel_cancel,
        pattern='^cancel_cancel$'
    ))

    # 5. 返回列表菜单
    dp.add_handler(CallbackQueryHandler(
        show_lottery_list_main,
        pattern='^lottery_list_main$'
    ))
