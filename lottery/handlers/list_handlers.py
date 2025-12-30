# lottery/handlers/list_handlers.py
"""
抽奖列表（正在进行 / 已结束）+ 分页 + 取消抽奖
"""

from datetime import timedelta
from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from telegram import Update
from lottery.services.scheduler_service import get_scheduler

from common.keyboards import append_back_button
from lottery.models import Lottery

PAGE_SIZE = 5


# ============================
# 抽奖列表主菜单
# ============================
def show_lottery_list_main(update: Update, context: CallbackContext):
    """显示抽奖列表主菜单（正在进行/已结束）"""
    query = update.callback_query
    query.answer()

    # 清除对话状态（如果有）
    from common.utils import end_all_conversations
    end_all_conversations(context)

    keyboard = [
        [InlineKeyboardButton("🔄 正在进行", callback_data="lottery:list:ongoing:1")],
        [InlineKeyboardButton("📅 已结束", callback_data="lottery:list:ended:1")],
        [InlineKeyboardButton("🔙 返回抽奖管理", callback_data="lottery:menu")],
    ]
    reply_markup = append_back_button(keyboard)

    query.edit_message_text(
        text="🎟️ 抽奖列表\n请选择查看类型：",
        reply_markup=reply_markup
    )


# ============================
# 工具：生成列表文本 + 键盘
# ============================
def generate_lottery_list_message(lotteries, page, is_ongoing, total):
    text_parts = []

    title = "🔄 正在进行的抽奖" if is_ongoing else "📅 已结束的抽奖（近1个月）"
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    text_parts.append(f"{title}\n第 {page} 页 / 共 {total_pages} 页\n\n")

    if not lotteries:
        text_parts.append("暂无抽奖记录。")
        keyboard = [[InlineKeyboardButton("🔙 返回列表菜单", callback_data="lottery:list:main")]]
        return "".join(text_parts), InlineKeyboardMarkup(keyboard)

    # 列表内容
    for idx, lottery in enumerate(lotteries, 1):
        status = "🔄 进行中" if is_ongoing else "✅ 已开奖"
        prize_info = lottery.prizes.first().name if lottery.prizes.exists() else "无"

        text_parts.append(
            f"{idx}. **{lottery.title}**\n"
            f"   📅 截止时间：{lottery.end_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"   🏆 奖品：{prize_info}\n"
            f"   📝 状态：{status}\n\n"
        )

    keyboard = []

    # 正在进行的抽奖 → 显示取消按钮
    if is_ongoing:
        for lottery in lotteries:
            keyboard.append([
                InlineKeyboardButton(
                    f"🚫 取消[{lottery.title}]",
                    callback_data=f"lottery:cancel:confirm:{lottery.id}"
                )
            ])

    # 分页按钮
    pagination = []
    if page > 1:
        pagination.append(
            InlineKeyboardButton(
                "⬅️ 上一页",
                callback_data=f"lottery:list:{'ongoing' if is_ongoing else 'ended'}:{page - 1}"
            )
        )
    if page * PAGE_SIZE < total:
        pagination.append(
            InlineKeyboardButton(
                "➡️ 下一页",
                callback_data=f"lottery:list:{'ongoing' if is_ongoing else 'ended'}:{page + 1}"
            )
        )
    if pagination:
        keyboard.append(pagination)

    keyboard.append([InlineKeyboardButton("🔙 返回列表菜单", callback_data="lottery:list:main")])
    reply_markup = append_back_button(keyboard)

    return "".join(text_parts), reply_markup


# ============================
# 分页显示抽奖列表
# ============================
def show_lottery_page(update: Update, context: CallbackContext, is_ongoing: bool, page: int = 1):
    query = update.callback_query
    query.answer()

    chat_id = query.message.chat_id
    message_id = query.message.message_id

    PAGE_SIZE = 5
    offset = (page - 1) * PAGE_SIZE

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
    current = lotteries[offset:offset + PAGE_SIZE]

    text, reply_markup = generate_lottery_list_message(current, page, is_ongoing, total)

    try:
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except:
        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


# ============================
# 正在进行 / 已结束入口
# ============================
def handle_ongoing_lotteries(update: Update, context: CallbackContext):
    show_lottery_page(update, context, is_ongoing=True, page=1)


def handle_ended_lotteries(update: Update, context: CallbackContext):
    show_lottery_page(update, context, is_ongoing=False, page=1)


# ============================
# 分页按钮
# ============================
def handle_lottery_pagination(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(":")

    # lottery:list:ongoing:2
    _, _, lottery_type, page = parts

    is_ongoing = (lottery_type == "ongoing")
    show_lottery_page(update, context, is_ongoing, int(page))


# ============================
# 取消抽奖（确认）
# ============================
def confirm_cancel_lottery(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    # lottery:cancel:confirm:12
    lottery_id = query.data.split(":")[-1]
    context.user_data["cancel_lottery_id"] = lottery_id

    keyboard = [
        [InlineKeyboardButton("✅ 确认取消", callback_data="lottery:cancel:do")],
        [InlineKeyboardButton("❌ 取消操作", callback_data="lottery:cancel:back")],
    ]

    query.edit_message_text(
        "⚠️ 确认取消抽奖？取消后将删除抽奖记录并停止开奖任务。",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================
# 执行取消抽奖
# ============================
def do_cancel_lottery(update: Update, context: CallbackContext):
    scheduler = get_scheduler()
    query = update.callback_query
    query.answer()

    lottery_id = context.user_data.get("cancel_lottery_id")
    if not lottery_id:
        query.edit_message_text("❌ 取消失败：未找到抽奖记录。")
        return

    try:
        lottery = Lottery.objects.get(
            id=lottery_id,
            is_active=True,
            is_drawn=False,
            end_time__gt=timezone.now()
        )

        job_id = f"lottery_draw_{lottery.id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        lottery.delete()

        keyboard = [[InlineKeyboardButton("🔙 返回抽奖列表", callback_data="lottery:list:ongoing:1")]]
        query.edit_message_text(
            f"✅ 抽奖《{lottery.title}》已成功取消！",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Lottery.DoesNotExist:
        query.edit_message_text("❌ 取消失败：抽奖不存在或已结束。")
    except Exception as e:
        query.edit_message_text(f"❌ 取消失败：{e}")


# ============================
# 取消取消操作
# ============================
def cancel_cancel(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    show_lottery_page(update, context, is_ongoing=True, page=1)
