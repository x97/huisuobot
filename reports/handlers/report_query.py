# bot_core/handlers/report_query.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, MessageHandler, Filters, CallbackQueryHandler

from django.db.models import Q
from django.core.paginator import Paginator

from reports.models import Report
from places.services import get_all_place_names, find_place_by_name



# ============================
# 2. 报告查询
# ============================

def query_reports_by_place_names(name_list):
    return Report.objects.filter(
        place_name__in=name_list,
        status="approved"
    ).order_by("-published_at", "-created_at")


def fallback_query_reports(query_name):
    return Report.objects.filter(
        place_name=query_name,
        status="approved"
    ).order_by("-published_at", "-created_at")


# ============================
# 3. 分页按钮
# ============================

def build_pagination_keyboard(place_key, page, total_pages):
    buttons = []

    if page > 1:
        buttons.append(
            InlineKeyboardButton("⬅ 上一条", callback_data=f"report:{place_key}:{page-1}")
        )

    if page < total_pages:
        buttons.append(
            InlineKeyboardButton("下一条 ➡", callback_data=f"report:{place_key}:{page+1}")
        )

    return InlineKeyboardMarkup([buttons]) if buttons else None


# ============================
# 4. 发送报告内容
# ============================

def format_report_text(report, place=None):
    text = f"📄 报告 #{report.id}\n"

    if place:
        text += f"🏠 场所：{place.name}\n"

    text += f"📝 内容：{report.content}\n"
    text += f"📅 时间：{report.published_at or report.created_at}\n"

    return text


def send_report_page(update, context, reports, page, place, place_key):
    paginator = Paginator(reports, 1)
    page_obj = paginator.get_page(page)
    report = page_obj.object_list[0]

    text = format_report_text(report, place)

    keyboard = build_pagination_keyboard(place_key, page, paginator.num_pages)

    if report.image:
        update.message.reply_photo(
            photo=report.image.url,
            caption=text,
            reply_markup=keyboard
        )
    else:
        update.message.reply_text(text, reply_markup=keyboard)


# ============================
# 5. 主查询 Handler
# ============================

def report_query_handler(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    if not text.startswith("报告#"):
        return

    query_name = text.split("#", 1)[1].strip()

    # 查找场所
    place = find_place_by_name(query_name)

    if place:
        name_list = get_all_place_names(place)
        reports = query_reports_by_place_names(name_list)
        place_key = place.name  # 用主名称作为 key
    else:
        reports = fallback_query_reports(query_name)
        place_key = query_name

    if not reports.exists():
        update.message.reply_text(f"未找到与 {query_name} 相关的报告")
        return

    send_report_page(update, context, reports, page=1, place=place, place_key=place_key)


# ============================
# 6. 分页 Callback Handler
# ============================

def report_pagination_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    _, place_key, page = query.data.split(":")
    page = int(page)

    # 查找场所
    place = find_place_by_name(place_key)
    if place:
        name_list = get_all_place_names(place)
        reports = query_reports_by_place_names(name_list)
    else:
        reports = fallback_query_reports(place_key)

    paginator = Paginator(reports, 1)
    page_obj = paginator.get_page(page)
    report = page_obj.object_list[0]

    text = format_report_text(report, place)
    keyboard = build_pagination_keyboard(place_key, page, paginator.num_pages)
    query.edit_message_text(text, reply_markup=keyboard)


# ============================
# 7. 注册 Handlers
# ============================

def register_report_handlers(dp):
    # 只匹配以“报告#”开头的消息
    dp.add_handler(MessageHandler(
        Filters.regex(r"^报告#.+"),
        report_query_handler
    ))

    # 分页按钮
    dp.add_handler(CallbackQueryHandler(
        report_pagination_callback,
        pattern=r"^report:"
    ))
