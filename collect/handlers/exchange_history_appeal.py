import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CommandHandler,
)

from collect.models import ExchangeRecord
from tgusers.models import TelegramUser
from common.callbacks import make_cb
from common.keyboards import append_back_button
from collect.handlers.status_code import APPEAL_WAITING_REASON, APPEAL_WAITING_CONFIRM

logger = logging.getLogger(__name__)

PREFIX = "exchange"
PAGE_SIZE = 3


def _build_history_text_and_buttons(records, page, total_pages):
    """
    返回 (text, InlineKeyboardMarkup)
    """
    lines = [f"兑换历史（第 {page}/{total_pages} 页）：\n"]
    buttons = []

    for rec in records:
        place_name = rec.place.name if rec.place else "已删除场所"
        created = rec.created_at.strftime("%Y-%m-%d")
        lines.append(f"{rec.id:>2d}.  💎{place_name} | ⭐{rec.points:>4}分 |"
                     f" 🚩{rec.status_show} | 📅{created}")

        row = []

        # ① 查看详情按钮（仅当状态可查看）
        if rec.status in ("completed", "approved"):
            row.append(
                InlineKeyboardButton(
                    "🔍 查看详情",
                    callback_data=make_cb(PREFIX, "detail", rec.id)
                )
            )
        else:
            row.append(
                InlineKeyboardButton(
                    "❌ 不可查看",
                    callback_data=make_cb(PREFIX, "noop", rec.id)
                )
            )

        # ② 申诉按钮（仅 completed 可申诉）
        if rec.status == "completed":
            row.append(
                InlineKeyboardButton(
                    f"申诉编号{rec.id} ",
                    callback_data=make_cb(PREFIX, "appeal", rec.id)
                )
            )
        else:
            row.append(
                InlineKeyboardButton(
                    f"{rec.status_show}积分",
                    callback_data=make_cb(PREFIX, "noop", rec.id)
                )
            )

        # 将两个按钮放在同一行
        buttons.append(row)

    # 分页导航
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=make_cb(PREFIX, "history", page - 1)))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("下一页 ➡️", callback_data=make_cb(PREFIX, "history", page + 1)))
    if nav_row:
        buttons.append(nav_row)

    # 返回主菜单
    base_markup = InlineKeyboardMarkup(buttons)
    final_markup = append_back_button(base_markup)
    return "\n".join(lines), final_markup


def exchange_history_handler(update: Update, context: CallbackContext):
    """
    回调入口：exchange:history 或 exchange:history:<page>
    显示分页的兑换历史（每页 PAGE_SIZE 条），并在每条记录下方放置对应的申诉按钮。
    """
    query = update.callback_query
    if query:
        query.answer()
        data = query.data
    else:
        # 也支持命令或文本触发（不常用）
        data = make_cb(PREFIX, "history", 1)

    # 解析页码（默认 1）
    parts = data.split(":")
    page = 1
    try:
        if len(parts) >= 3:
            page = int(parts[-1])
    except Exception:
        page = 1

    user = update.effective_user
    tg_user = TelegramUser.objects.filter(user_id=user.id).first()
    if not tg_user:
        text = "未找到用户信息，请先与 bot 交互。"
        if query:
            query.edit_message_text(text)
        else:
            update.message.reply_text(text)
        return

    qs = ExchangeRecord.objects.filter(user=tg_user).order_by("-created_at")
    total = qs.count()
    if total == 0:
        text = "你还没有兑换记录。"
        if query:
            query.edit_message_text(text)
        else:
            update.message.reply_text(text)
        return

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_records = list(qs[start:end])

    text, markup = _build_history_text_and_buttons(page_records, page, total_pages)

    try:
        if query:
            query.edit_message_text(text, reply_markup=markup)
        else:
            update.message.reply_text(text, reply_markup=markup)
    except Exception:
        # 回退为发送新消息
        if query:
            context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=markup)
        else:
            update.message.reply_text(text, reply_markup=markup)


def exchange_appeal_start(update: Update, context: CallbackContext):
    """
    点击某条记录的申诉按钮后进入此处（callback_data = exchange:appeal:<record_id>）
    提示用户输入申诉理由并进入 APPEAL_WAITING_REASON 状态
    """
    query = update.callback_query
    if not query:
        return ConversationHandler.END  # 修复：非回调触发直接结束会话
    query.answer()
    parts = query.data.split(":")
    try:
        record_id = int(parts[-1])
    except Exception:
        query.answer("参数错误", show_alert=True)
        return ConversationHandler.END

    record = ExchangeRecord.objects.filter(id=record_id).first()
    if not record:
        query.answer("记录不存在", show_alert=True)
        return ConversationHandler.END

    # 只有 completed 状态允许用户发起申诉
    if record.status != "completed":
        query.answer("该记录当前不可申诉。", show_alert=True)
        return ConversationHandler.END

    # 保存 record_id 到上下文，等待用户输入理由
    context.user_data['appeal_record_id'] = record_id
    prompt = (
        f"你正在对兑换记录 {record.id} 发起申诉。\n"
        "请在下一条消息中输入申诉理由（简要说明为何需要退回积分），发送后会要求你确认提交。\n"
        "发送 /cancel 取消当前操作"  # 修复：添加换行，优化格式
    )
    try:
        query.edit_message_text(prompt)
    except Exception:
        context.bot.send_message(chat_id=query.message.chat_id, text=prompt)
    return APPEAL_WAITING_REASON  # 修复：明确返回状态，维持会话


def handle_non_text_input(update: Update, context: CallbackContext):
    """新增：处理用户发送的非文本内容（图片/文件/贴纸等）"""
    update.message.reply_text("📝 申诉理由仅支持文字输入，请重新发送文本内容！")
    return APPEAL_WAITING_REASON


def exchange_appeal_receive_reason(update: Update, context: CallbackContext):
    """
    接收用户输入的申诉理由，显示确认按钮（确认提交或取消）
    """
    text = update.message.text.strip()
    if not text:
        update.message.reply_text("申诉理由不能为空，请重新输入。")
        return APPEAL_WAITING_REASON

    record_id = context.user_data.get('appeal_record_id')
    if not record_id:
        update.message.reply_text("会话已过期或参数缺失，请重新发起申诉。")
        return ConversationHandler.END

    # 新增：校验记录是否仍有效
    record = ExchangeRecord.objects.filter(id=record_id, status="completed").first()
    if not record:
        update.message.reply_text("⚠️ 该记录已不可申诉，请重新发起！")
        context.user_data.pop('appeal_record_id', None)
        return ConversationHandler.END

    # 保存理由到上下文，等待确认
    context.user_data['appeal_reason_text'] = text

    confirm_cb = make_cb(PREFIX, "appeal_submit", record_id)
    cancel_cb = make_cb("core", "back_main")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 提交申诉", callback_data=confirm_cb)],
        [InlineKeyboardButton("🔙 取消", callback_data=cancel_cb)],
    ])

    preview = f"⌨️你输入的申诉理由：\n\n{text}"
    update.message.reply_text(preview, reply_markup=keyboard)
    return APPEAL_WAITING_CONFIRM  # 修复：确保返回状态，进入确认步骤


def exchange_appeal_submit(update: Update, context: CallbackContext):
    """
    用户确认提交申诉（callback_data = exchange:appeal_submit:<record_id>）
    将记录标记为 appealed 并保存理由与时间
    """
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    query.answer()
    parts = query.data.split(":")
    try:
        record_id = int(parts[-1])
    except Exception:
        query.answer("参数错误", show_alert=True)
        return ConversationHandler.END

    reason = context.user_data.get('appeal_reason_text', "").strip()
    if not reason:
        query.answer("申诉理由缺失，请重新发起。", show_alert=True)
        return ConversationHandler.END

    record = ExchangeRecord.objects.filter(id=record_id).first()
    if not record:
        query.edit_message_text("记录不存在或已被删除。")
        return ConversationHandler.END

    # 仅当状态为 completed 时允许提交申诉
    if record.status != "completed":
        query.edit_message_text("该记录当前不可申诉。")
        return ConversationHandler.END

    # 保存申诉信息（事务）
    with transaction.atomic():
        record.appeal_reason = reason
        record.appeal_at = timezone.now()
        record.status = "appealed"
        record.save(update_fields=["appeal_reason", "appeal_at", "status"])

    try:
        query.edit_message_text("申诉已提交，管理员会尽快处理。", reply_markup=append_back_button(None))
    except Exception:
        context.bot.send_message(chat_id=query.message.chat_id, text="申诉已提交，管理员会尽快处理。",
                                 reply_markup=append_back_button(None))

    # 清理上下文
    context.user_data.pop('appeal_record_id', None)
    context.user_data.pop('appeal_reason_text', None)
    return ConversationHandler.END


def noop_callback(update: Update, context: CallbackContext):
    """占位回调，处理不可用按钮点击（避免无响应）"""
    query = update.callback_query
    if not query:
        return
    query.answer("该操作当前不可用。", show_alert=True)


def cancel_appeal(update: Update, context: CallbackContext):
    """
    通用取消处理：支持用户输入 /cancel 或点击返回主菜单（core:back_main）
    """
    # 如果是回调（按钮触发）
    if update.callback_query:
        q = update.callback_query
        q.answer()
        try:
            q.edit_message_text("已取消。")
        except Exception:
            context.bot.send_message(chat_id=q.message.chat_id, text="已取消。")
    else:
        # 如果是命令 /cancel
        try:
            update.message.reply_text("已取消。")
        except Exception:
            pass

    # 清理会话上下文中可能残留的数据
    context.user_data.pop('appeal_record_id', None)
    context.user_data.pop('appeal_reason_text', None)
    return ConversationHandler.END

def exchange_detail_handler(update: Update, context: CallbackContext):
    """查看兑换记录详情（展示前 3 个真实联系方式）"""
    query = update.callback_query
    if not query:
        return

    query.answer()
    parts = query.data.split(":")
    try:
        record_id = int(parts[-1])
    except Exception:
        query.answer("参数错误", show_alert=True)
        return

    rec = ExchangeRecord.objects.filter(id=record_id).first()
    if not rec:
        query.edit_message_text("记录不存在或已被删除。")
        return

    # 不可查看的状态
    if rec.status not in ("completed", "approved"):
        query.answer("该记录当前不可查看详情。", show_alert=True)
        return

    place = rec.place
    if not place:
        query.edit_message_text("该记录的场所信息已被删除。")
        return

    # 获取前 3 个营销信息（与兑换时逻辑一致）
    marketings = list(place.marketings.all())
    if not marketings:
        query.edit_message_text("该场所的营销信息已被删除。")
        return

    show_count = min(3, len(marketings))
    show_marketings = marketings[:show_count]

    # 构建展示文本
    lines = [
        f"📄 兑换记录详情（ID: {rec.id}）",
        f"场所: {place.name}",
        f"积分: {rec.points}",
        f"状态: {rec.status_show}",
        f"时间: {rec.created_at.strftime('%Y-%m-%d %H:%M')}",
        "---------------------------------",
        "以下为该场所的真实联系方式：",
    ]

    for idx, m in enumerate(show_marketings, start=1):
        real_phone = m.phone or "无"
        real_wechat = m.wechat or "无"
        lines.append(f"{idx}. 营销名: {m.name}")
        lines.append(f"☎️ 电话: {real_phone}    🛰️微信: {real_wechat}")
        lines.append("")

    text = "\n".join(lines)

    try:
        query.edit_message_text(text, reply_markup=append_back_button(None))
    except Exception:
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=append_back_button(None)
        )

def get_history_appeal_conversation_handler() -> ConversationHandler:
    """
    返回 ConversationHandler，用于注册：
    - entry: exchange:history 或 command /history_exchange
    - states: APPEAL_WAITING_REASON, APPEAL_WAITING_CONFIRM
    支持用户输入 /cancel 取消当前操作
    """
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(exchange_history_handler, pattern=rf"^{PREFIX}:history(?::\d+)?$"),
            CommandHandler("history_exchange", exchange_history_handler),
            CallbackQueryHandler(exchange_appeal_start, pattern=rf"^{PREFIX}:appeal:\d+$"),  # ← 加上这个
        ],

        states={
            APPEAL_WAITING_REASON: [
                # 修复：放宽过滤器，允许所有文本（包括表情/链接），仅排除命令
                MessageHandler(Filters.text, exchange_appeal_receive_reason),
                # 新增：处理非文本输入，避免会话中断
                MessageHandler(Filters.all & ~Filters.text, handle_non_text_input),
                CommandHandler("cancel", cancel_appeal),
            ],
            APPEAL_WAITING_CONFIRM: [
                CallbackQueryHandler(exchange_appeal_submit, pattern=rf"^{PREFIX}:appeal_submit:\d+$"),
                CommandHandler("cancel", cancel_appeal),
                # 新增：处理返回主菜单的回调
                CallbackQueryHandler(cancel_appeal, pattern=rf"^core:back_main$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_appeal),
            CallbackQueryHandler(cancel_appeal, pattern=rf"^core:back_main$"),
        ],
        per_user=True,
        # 新增：添加会话超时，避免上下文残留
        conversation_timeout=300,  # 5分钟超时
    )
    return conv


def register_history_appeal_handlers(dispatcher):
    """
    在 bot 启动时调用此函数注册 handlers：
    - 会话 handlers（分页历史 + 申诉对话）
    - 单独的申诉入口（点击申诉按钮）
    - noop 回调（处理不可用按钮）
    修复：删除重复的处理器注册，避免覆盖会话内的逻辑
    """
    # 注册会话处理器（核心，包含所有状态流转）
    dispatcher.add_handler(get_history_appeal_conversation_handler())
    # 仅注册noop回调（处理不可用按钮）
    dispatcher.add_handler(CallbackQueryHandler(noop_callback, pattern=rf"^{PREFIX}:noop:\d+$"))
    # 移除以下重复注册的代码，因为ConversationHandler内部已处理
    dispatcher.add_handler(CallbackQueryHandler(exchange_history_handler, pattern=rf"^{PREFIX}:history(?::\d+)?$"))
    dispatcher.add_handler(CallbackQueryHandler(exchange_appeal_submit, pattern=rf"^{PREFIX}:appeal_submit:\d+$"))
    #查看兑换详情
    dispatcher.add_handler(CallbackQueryHandler(exchange_detail_handler, pattern=rf"^{PREFIX}:detail:\d+$"))
