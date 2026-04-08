# collect/handlers/reward_review.py

import logging
from django.utils import timezone
from django.conf import settings
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from mygroups.models import MyGroup
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
)

from collect.models import Submission, SubmissionPhoto
from places.models import Staff
from common.callbacks import make_cb
from common.keyboards import append_back_button

logger = logging.getLogger(__name__)

PREFIX = "reward_review"

# Conversation states
REVIEWING_PHOTO = 1
REJECTING_TEXT = 2


# ============================
# 🔥 全局安全编辑函数
# ============================
def safe_edit(query, text, keyboard=None):
    """
    自动根据消息类型选择 edit_message_text 或 edit_message_caption
    """
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


# ============================
# 🔥 列出待审核提交
# ============================
def admin_list_pending(update: Update, context: CallbackContext):
    pending = Submission.objects.filter(status="pending").order_by("-created_at")

    if not pending.exists():
        if update.callback_query:
            safe_edit(update.callback_query, "暂无待审核的悬赏提交。")
        else:
            update.message.reply_text("暂无待审核的悬赏提交。")
        return ConversationHandler.END

    for sub in pending[:20]:
        text = (
            f"提交ID: {sub.id}\n"
            f"活动: {sub.campaign.title}\n"
            f"提交人: {sub.reporter}\n\n"
            f"【场所名称】{sub.place_name}\n"
            f"【技师号码】{sub.nickname}\n"
            f"【出生年份】{sub.birth_year}\n"
            f"【胸围大小】{sub.bust_size}\n"
            f"【胸围信息】{sub.bust_info}\n"
            f"【颜值评价】{sub.attractiveness}\n"
            f"【补充信息】{sub.extra_info}\n\n"
            f"📸 照片数量：{sub.photos.count()}"
        )

        # 按钮逻辑：有照片 → 查看照片；无照片 → 直接通过
        if sub.photos.count() > 0:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📷 查看照片", callback_data=make_cb(PREFIX, "photos", sub.id)),
                    InlineKeyboardButton("❌ 拒绝", callback_data=make_cb(PREFIX, "reject", sub.id)),
                ]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ 通过", callback_data=make_cb(PREFIX, "approve", sub.id)),
                    InlineKeyboardButton("❌ 拒绝", callback_data=make_cb(PREFIX, "reject", sub.id)),
                ]
            ])

        if update.callback_query:
            safe_edit(update.callback_query, text, keyboard)
        else:
            update.message.reply_text(text, reply_markup=keyboard)

    return ConversationHandler.END


# ============================
# 🔥 进入照片审核
# ============================
def admin_review_photos(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    _, _, sub_id = query.data.split(":")
    sub_id = int(sub_id)

    context.user_data["review_sub_id"] = sub_id
    context.user_data["photo_index"] = 0

    return _show_photo(update, context)


# ============================
# 🔥 显示当前照片（核心）
# ============================
def _show_photo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    sub_id = context.user_data["review_sub_id"]
    index = context.user_data["photo_index"]

    sub = Submission.objects.get(id=sub_id)
    photos = list(sub.photos.all())

    # 没有照片 → 返回信息审核
    if not photos:
        safe_edit(
            query,
            "该提交没有照片。\n请继续审核文字信息。",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("继续审核文字信息", callback_data=make_cb(PREFIX, "info", sub_id))]
            ])
        )
        return ConversationHandler.END

    # 所有照片审核完毕
    if index >= len(photos):
        safe_edit(
            query,
            "📸 所有照片已审核完毕。\n请继续审核文字信息。",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("继续审核文字信息", callback_data=make_cb(PREFIX, "info", sub_id))]
            ])
        )
        return ConversationHandler.END

    photo = photos[index]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍 通过此照片", callback_data=make_cb(PREFIX, "photo_approve", photo.id)),
            InlineKeyboardButton("👎 拒绝此照片", callback_data=make_cb(PREFIX, "photo_reject", photo.id)),
        ],
        [
            InlineKeyboardButton("下一张", callback_data=make_cb(PREFIX, "next_photo", sub_id))
        ]
    ])

    # 使用 reply_photo，不使用 edit_message_media
    query.message.reply_photo(
        photo.image,
        caption=f"照片 {index+1}/{len(photos)}",
        reply_markup=keyboard
    )

    return REVIEWING_PHOTO


# ============================
# 🔥 单张照片审核
# ============================
def admin_photo_approve(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    photo_id = int(query.data.split(":")[-1])
    photo = SubmissionPhoto.objects.get(id=photo_id)
    photo.status = "approved"
    photo.save()

    return _next_photo(update, context)


def admin_photo_reject(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    photo_id = int(query.data.split(":")[-1])
    photo = SubmissionPhoto.objects.get(id=photo_id)
    photo.status = "rejected"
    photo.save()

    return _next_photo(update, context)


def admin_next_photo(update: Update, context: CallbackContext):
    return _next_photo(update, context)


def _next_photo(update: Update, context: CallbackContext):
    context.user_data["photo_index"] += 1
    return _show_photo(update, context)


# ============================
# 🔥 返回信息审核界面
# ============================
def admin_review_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    sub_id = int(query.data.split(":")[-1])
    sub = Submission.objects.get(id=sub_id)

    # 检查是否所有照片都审核完毕
    if sub.photos.filter(status="pending").exists():
        safe_edit(
            query,
            "⚠️ 还有未审核的照片，请先完成照片审核。",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("继续审核照片", callback_data=make_cb(PREFIX, "photos", sub_id))]
            ])
        )
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 通过信息", callback_data=make_cb(PREFIX, "approve", sub_id)),
            InlineKeyboardButton("❌ 拒绝信息", callback_data=make_cb(PREFIX, "reject", sub_id)),
        ]
    ])

    safe_edit(
        query,
        (
            "📄 信息审核：\n\n"
            f"【场所名称】{sub.place_name}\n"
            f"技师号码：{sub.nickname}\n"
            f"出生年份：{sub.birth_year}\n"
            f"胸围大小：{sub.bust_size}\n"
            f"胸围信息：{sub.bust_info}\n"
            f"颜值评价：{sub.attractiveness}\n"
            f"补充信息：{sub.extra_info}\n\n"
            "📸 照片审核已完成。"
        ),
        keyboard
    )

    return ConversationHandler.END


# ============================
# 🔥 信息审核通过
# ============================
# ============================
# 🔥 信息审核通过（已改造：支持 place_name + 自动查找场所）
# ============================
from places.services import find_place_by_name  # 请确保顶部已导入

# ============================
# 🔥 审核通过 → 自动评论：文字+照片+完整按钮
# ============================
def admin_approve(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    sub_id = int(query.data.split(":")[-1])
    sub = Submission.objects.get(id=sub_id)

    # 1. 查询场所
    place_name = sub.place_name
    place = find_place_by_name(place_name)

    if not place:
        safe_edit(
            query,
            f"❌ 无法通过审核\n\n"
            f"提交的场所名称：{place_name}\n"
            f"⚠️ 系统中不存在该场所，请先创建场所后再审核通过！",
            append_back_button(None)
        )
        return ConversationHandler.END

    # 2. 关联/创建 Staff
    staff = Staff.objects.filter(
        place=place,
        nickname=sub.nickname,
        is_active=True
    ).first()

    if not staff:
        staff = Staff.objects.create(
            place=place,
            nickname=sub.nickname,
            is_active=True
        )

    # 3. 保存审核
    sub.status = "approved"
    sub.staff = staff
    sub.reviewed_at = timezone.now()
    sub.save()

    # 发放金币
    reporter = sub.reporter
    reporter.points += sub.campaign.reward_coins
    reporter.save(update_fields=["points"])

    # 4. 发送频道评论（拆分出去的单独函数）
    send_submission_comment_to_channel(sub, staff, context.bot)

    # 5. 回复管理员
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 继续审核", callback_data="reward_review:list")]
    ])
    keyboard = append_back_button(keyboard)

    safe_edit(query, "🎉 审核通过！已自动发布到悬赏频道评论区。", keyboard)

    return ConversationHandler.END


# ============================
# ✉️ 单独拆分：频道评论发送函数
# ============================
from interactions.utils import render_submission
from .query_staff import build_staff_submission_keyboard

def send_submission_comment_to_channel(sub, staff, bot):
    try:
        notifications = sub.campaign.notifications.all()
        text = render_submission(sub)

        keyboard = build_staff_submission_keyboard(
            submission=sub,
            staff=staff,
            page=1,
            total_submissions=1,
            user_id=None
        )

        for notify in notifications:
            group = MyGroup.objects.filter(notify_channel_id=notify.notify_channel_id).first()
            if not group or not group.notify_discuss_group_id:
                continue

            discuss_group_id = group.notify_discuss_group_id

            # ✅ 使用你模型正确的字段
            bot.send_message(
                chat_id=discuss_group_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,

                # 官方正确评论方式
                reply_parameters={
                    "chat_id": notify.notify_channel_id,
                    "message_id": notify.message_id,
                }
            )

    except Exception as e:
        logger.warning(f"自动评论悬赏失败：{str(e)}")



# ============================
# 🔥 信息审核拒绝
# ============================
def admin_reject(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    sub_id = int(query.data.split(":")[-1])
    context.user_data["reject_sub_id"] = sub_id

    safe_edit(query, "请输入拒绝理由：")
    return REJECTING_TEXT


def admin_reject_reason(update: Update, context: CallbackContext):
    message = update.message
    reason = message.text.strip()

    sub_id = context.user_data.pop("reject_sub_id", None)
    if not sub_id:
        return ConversationHandler.END

    sub = Submission.objects.get(id=sub_id)

    sub.status = "rejected"
    sub.review_note = reason
    sub.reviewed_at = timezone.now()
    sub.save()

    sub.photos.update(status="rejected")

    message.reply_text(
        f"已拒绝该提交。\n拒绝理由：{reason}",
        reply_markup=append_back_button(None)
    )

    return ConversationHandler.END


# ============================
# 🔥 注册 handlers
# ============================
def register_reward_review_handlers(dispatcher):

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("review_reward", admin_list_pending),
            CallbackQueryHandler(admin_list_pending, pattern=r"^reward_review:list$"),
            CallbackQueryHandler(admin_review_photos, pattern=r"^reward_review:photos:\d+$"),
            CallbackQueryHandler(admin_review_info, pattern=r"^reward_review:info:\d+$"),
            CallbackQueryHandler(admin_photo_approve, pattern=r"^reward_review:photo_approve:\d+$"),
            CallbackQueryHandler(admin_photo_reject, pattern=r"^reward_review:photo_reject:\d+$"),
            CallbackQueryHandler(admin_next_photo, pattern=r"^reward_review:next_photo:\d+$"),
            CallbackQueryHandler(admin_approve, pattern=r"^reward_review:approve:\d+$"),
            CallbackQueryHandler(admin_reject, pattern=r"^reward_review:reject:\d+$"),
        ],
        states={
            REVIEWING_PHOTO: [
                CallbackQueryHandler(admin_photo_approve, pattern=r"^reward_review:photo_approve:\d+$"),
                CallbackQueryHandler(admin_photo_reject, pattern=r"^reward_review:photo_reject:\d+$"),
                CallbackQueryHandler(admin_next_photo, pattern=r"^reward_review:next_photo:\d+$"),
            ],
            REJECTING_TEXT: [
                MessageHandler(Filters.text & ~Filters.command, admin_reject_reason),
            ],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
    )

    dispatcher.add_handler(conv)
