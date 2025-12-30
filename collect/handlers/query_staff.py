# collect/handlers/query_staff.py

import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, Filters, CallbackQueryHandler
from collect.models import Submission, SubmissionPhoto
from places.models import Staff
from interactions.keyboards import build_submission_keyboard
from interactions.utils import render_submission, get_submission_page


QUERY_PATTERN = re.compile(r"(?:#(?P<place1>\S+))?\s*(?:#?(?P<nick1>\S+))?")


# ============================================================
# safe_edit：统一处理文本消息 / 照片消息
# ============================================================
def safe_edit(query, text, keyboard=None):
    msg = query.message

    if msg.photo:  # 当前消息是照片 → 只能编辑 caption
        return query.edit_message_caption(
            caption=text,
            reply_markup=keyboard
        )
    else:  # 当前消息是文本 → 只能编辑 text
        return query.edit_message_text(
            text=text,
            reply_markup=keyboard
        )


# ============================================================
# 构建技师投稿视图键盘
# ============================================================
def build_staff_submission_keyboard(submission, staff, page, total_submissions, user_id=None):
    base = build_submission_keyboard(submission, staff, user_id=user_id)
    rows = base.inline_keyboard

    # 投稿分页
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("上一条", callback_data=f"sub:page:{staff.id}:{page-1}"))
    if page < total_submissions:
        nav.append(InlineKeyboardButton("下一条", callback_data=f"sub:page:{staff.id}:{page+1}"))
    if nav:
        rows.append(nav)

    # 查看所有照片
    if SubmissionPhoto.objects.filter(submission__staff=staff).exists():
        rows.append([
            InlineKeyboardButton(
                "查看该技师所有照片",
                callback_data=f"staff_photos:{staff.id}:1"
            )
        ])

    return InlineKeyboardMarkup(rows)


# ============================================================
# 群聊查询入口
# ============================================================
def handle_group_query(update: Update, context: CallbackContext):
    if update.effective_chat.type not in ("group", "supergroup"):
        return

    text = update.message.text.strip()
    if not (text.startswith("查") or "#" in text):
        return

    m = QUERY_PATTERN.search(text)
    place = m.group("place1")
    nickname = m.group("nick1")

    if not place:
        return

    staff = Staff.objects.filter(place__name__icontains=place, is_active=True).first()
    if not staff:
        update.message.reply_text("未找到在职技师")
        return

    submissions = Submission.objects.filter(staff=staff, is_valid=True).order_by("-created_at")
    if not submissions.exists():
        update.message.reply_text("该技师暂无有效投稿")
        return

    page = 1
    submission = get_submission_page(submissions, page)
    text = render_submission(submission)
    keyboard = build_staff_submission_keyboard(submission, staff, page, submissions.count())

    update.message.reply_text(text, reply_markup=keyboard)


# ============================================================
# 查看技师所有照片（仍然 reply_photo，不用 safe_edit）
# ============================================================
from telegram import InputMediaPhoto

def staff_photos_view(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    _, staff_id_str, page_str = query.data.split(":")
    staff_id = int(staff_id_str)
    page = int(page_str)

    staff = Staff.objects.filter(id=staff_id, is_active=True).first()
    if not staff:
        safe_edit(query, "该技师已不存在或已离职。")
        return

    photos = SubmissionPhoto.objects.filter(
        submission__staff=staff,
        submission__is_valid=True
    ).select_related("submission").order_by("-submission__created_at", "id")

    total = photos.count()
    if total == 0:
        safe_edit(query, "该技师暂无照片。")
        return

    page = max(1, min(page, total))
    photo = photos[page - 1]

    place = staff.place
    caption = (
        f"技师：{staff.nickname}\n"
        f"照片 {page}/{total}\n"
        f"投稿时间：{photo.submission.created_at:%Y-%m-%d}\n\n"
        f"【所属场所】\n"
        f"{place.name}-{place.district}-{place.city}"
    )

    # 按钮
    buttons = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("上一张", callback_data=f"staff_photos:{staff_id}:{page-1}"))
    if page < total:
        nav.append(InlineKeyboardButton("下一张", callback_data=f"staff_photos:{staff_id}:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton("返回技师信息", callback_data=f"staff_submissions:{staff_id}:1")
    ])

    keyboard = InlineKeyboardMarkup(buttons)

    # ⭐ 判断当前消息是否是照片
    if query.message.photo:
        # 当前是照片 → 用 edit_message_media 替换照片
        query.edit_message_media(
            media=InputMediaPhoto(
                media=photo.image,
                caption=caption
            ),
            reply_markup=keyboard
        )
    else:
        # 当前是文字 → 第一次进入照片视图 → reply_photo
        query.message.reply_photo(
            photo=photo.image,
            caption=caption,
            reply_markup=keyboard
        )


# ============================================================
# 返回技师投稿视图（safe_edit）
# ============================================================
def staff_submissions_view(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    _, staff_id_str, page_str = query.data.split(":")
    staff_id = int(staff_id_str)
    page = int(page_str)

    staff = Staff.objects.filter(id=staff_id, is_active=True).first()
    if not staff:
        safe_edit(query, "该技师已不存在或已离职。")
        return

    submissions = Submission.objects.filter(staff=staff, is_valid=True).order_by("-created_at")
    if not submissions.exists():
        safe_edit(query, "该技师暂无有效投稿。")
        return

    submission = get_submission_page(submissions, page)
    text = render_submission(submission)
    keyboard = build_staff_submission_keyboard(submission, staff, page, submissions.count())

    safe_edit(query, text, keyboard)


# ============================================================
# 投稿分页（safe_edit）
# ============================================================
def staff_submission_page(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    _, _, staff_id_str, page_str = query.data.split(":")
    staff_id = int(staff_id_str)
    page = int(page_str)

    staff = Staff.objects.filter(id=staff_id, is_active=True).first()
    if not staff:
        safe_edit(query, "该技师已不存在或已离职。")
        return

    submissions = Submission.objects.filter(staff=staff, is_valid=True).order_by("-created_at")
    submission = get_submission_page(submissions, page)
    text = render_submission(submission)
    keyboard = build_staff_submission_keyboard(submission, staff, page, submissions.count())

    safe_edit(query, text, keyboard)


# ============================================================
# 注册 handlers
# ============================================================
def register_query_staff_handlers(dp):
    dp.add_handler(MessageHandler((Filters.regex(r"^查") | Filters.regex(r"#")) & Filters.chat_type.groups, handle_group_query))
    dp.add_handler(CallbackQueryHandler(staff_photos_view, pattern=r"^staff_photos:\d+:\d+$"))
    dp.add_handler(CallbackQueryHandler(staff_submissions_view, pattern=r"^staff_submissions:\d+:\d+$"))
    dp.add_handler(CallbackQueryHandler(staff_submission_page, pattern=r"^sub:page:\d+:\d+$"))
