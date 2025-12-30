# interactions/handlers.py

from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest

from collect.models import Submission
from places.models import Staff
from interactions.services import (
    handle_like, handle_dislike, handle_inactive_report
)
from interactions.utils import render_submission, get_submission_page

# ⭐ 引入你新的 keyboard + safe_edit
from collect.handlers.query_staff import build_staff_submission_keyboard, safe_edit


def handle_interaction_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    data = query.data.split(":")
    action = data[1]

    if action == "like":
        submission_id = int(data[2])
        submission = Submission.objects.get(id=submission_id)

        ok = handle_like(submission, query.from_user.id)
        if not ok:
            query.answer("你已经点过赞了", show_alert=True)
            return

        staff = submission.staff
        submissions = Submission.objects.filter(staff=staff, is_valid=True).order_by("-created_at")
        page = submissions.filter(id__gte=submission_id).count()

    elif action == "dislike":
        submission_id = int(data[2])
        submission = Submission.objects.get(id=submission_id)

        ok = handle_dislike(submission, query.from_user.id)
        if not ok:
            query.answer("你已经点过不赞了", show_alert=True)
            return

        staff = submission.staff
        submissions = Submission.objects.filter(staff=staff, is_valid=True).order_by("-created_at")
        page = submissions.filter(id__gte=submission_id).count()

    elif action == "inactive":
        staff_id = int(data[2])
        staff = Staff.objects.get(id=staff_id)

        ok = handle_inactive_report(staff, query.from_user.id)
        if not ok:
            query.answer("你已经反馈过该技师离职情况了", show_alert=True)
            return

        submissions = Submission.objects.filter(staff=staff, is_valid=True).order_by("-created_at")
        page = 1

    else:
        return

    # ⭐ 渲染当前 submission
    submission = get_submission_page(submissions, page)
    text = render_submission(submission)

    # ⭐ 使用带分页 + 查看照片的 keyboard
    keyboard = build_staff_submission_keyboard(
        submission,
        staff,
        page,
        submissions.count(),
        user_id=query.from_user.id
    )

    # ⭐ 使用 safe_edit 替代 edit_message_text
    try:
        safe_edit(query, text, keyboard)
    except BadRequest:
        pass


def register_interaction_handlers(dp):
    dp.add_handler(CallbackQueryHandler(handle_interaction_callback, pattern=r"^sub:"))
