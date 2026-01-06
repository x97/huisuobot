import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    Filters,
    ConversationHandler,
)

from places.models import Place, Staff
from collect.models import Submission, SubmissionPhoto
from tgusers.services import update_or_create_user
from common.keyboards import append_back_button
from django.core.files.base import ContentFile


# ============================
# 🔥 ConversationHandler 状态
# ============================
TYPING = 1
UPLOADING_PHOTOS = 2
CONFIRMING = 3

ADMIN_STAFF_FIELDS = {
    "会所名称": "place_name",
    "技师号码": "nickname",
    "出生年份": "birth_year",
    "胸围大小": "bust_size",
    "胸围信息": "bust_info",
    "颜值信息": "attractiveness",
    "其他信息": "extra_info",
}


# ============================
# 🔥 1. 管理员点击按钮 → 进入创建流程
# ============================
def admin_add_staff_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    tguser = update_or_create_user(update.effective_user)
    if not tguser.is_admin:
        query.message.reply_text("❌ 你不是管理员，无权使用此功能", reply_markup=append_back_button(None))
        return ConversationHandler.END

    template = (
        "请按照以下格式填写技师信息：\n\n"
        "【会所名称】: \n"
        "【技师号码】: \n"
        "【出生年份】: \n"
        "【胸围大小】: \n"
        "【胸围信息】: \n"
        "【颜值信息】: \n"
        "【其他信息】: \n\n"
        "请直接复制以上模板并填写后发送给我。\n\n"
        "如需取消，请发送 /cancel"
    )

    query.message.reply_text(template)
    return TYPING


# ============================
# 🔥 2. 管理员取消流程
# ============================
def admin_add_staff_cancel(update: Update, context: CallbackContext):
    update.message.reply_text("已取消技师创建流程。", reply_markup=append_back_button(None))
    context.user_data.clear()
    return ConversationHandler.END


# ============================
# 🔥 3. 管理员填写模板 → 自动解析并进入上传照片阶段
# ============================
def admin_add_staff_receive(update: Update, context: CallbackContext):
    message = update.message
    if not message or not message.text:
        return TYPING

    text = message.text.strip()

    # 管理员判断
    tguser = update_or_create_user(update.effective_user)
    if not tguser.is_admin:
        return TYPING

    # 模板校验
    missing = [label for label in ADMIN_STAFF_FIELDS if f"【{label}】" not in text]
    if missing:
        message.reply_text(
            "⚠️ 你发送的内容不符合模板格式，请复制模板并填写后再发送。\n\n"
            "如需取消，请发送 /cancel"
        )
        return TYPING

    # 解析
    parsed = {}
    for label, field in ADMIN_STAFF_FIELDS.items():
        pattern = rf"【{label}】:\s*([^\n]*)"
        match = re.search(pattern, text)
        parsed[field] = match.group(1).strip() if match else ""

    context.user_data["admin_add_staff_data"] = parsed
    context.user_data["admin_add_staff_photos"] = []

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 不上传照片，直接确认", callback_data="staff_admin:skip_photos")]
    ])

    message.reply_text(
        "📸 你可以继续上传 1～5 张照片（可选）。\n"
        "如需取消，请发送 /cancel",
        reply_markup=keyboard
    )

    return UPLOADING_PHOTOS


# ============================
# 🔥 4. 管理员上传照片
# ============================
def admin_add_staff_receive_photo(update: Update, context: CallbackContext):
    photos = context.user_data.get("admin_add_staff_photos", [])

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        photos.append(file_id)
        context.user_data["admin_add_staff_photos"] = photos

        update.message.reply_text(
            f"📸 已收到照片，目前共 {len(photos)} 张。\n"
            "继续发送照片，或点击下方按钮跳过上传。",
        )

    return UPLOADING_PHOTOS


# ============================
# 🔥 5. 跳过上传照片 → 进入预览
# ============================
def admin_add_staff_skip_photos(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    parsed = context.user_data.get("admin_add_staff_data")
    photos = context.user_data.get("admin_add_staff_photos", [])

    preview = (
        "📋 <b>技师信息预览</b>\n\n"
        f"🏠 <b>会所：</b>{parsed['place_name']}\n"
        f"🔢 <b>技师号码：</b>{parsed['nickname']}\n"
        f"🎂 <b>出生年份：</b>{parsed['birth_year']}\n"
        f"💗 <b>胸围大小：</b>{parsed['bust_size']}\n"
        f"💗 <b>胸围信息：</b>{parsed['bust_info']}\n"
        f"😍 <b>颜值信息：</b>{parsed['attractiveness']}\n"
        f"📝 <b>其他信息：</b>{parsed['extra_info']}\n\n"
        f"📸 <b>照片数量：</b>{len(photos)}\n\n"
        "请确认是否创建该技师。"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认创建", callback_data="staff_admin:confirm"),
            InlineKeyboardButton("❌ 取消", callback_data="staff_admin:cancel_preview"),
        ]
    ])

    query.message.edit_text(preview, parse_mode="HTML", reply_markup=keyboard)
    return CONFIRMING


# ============================
# 🔥 6. 管理员确认创建
# ============================
def admin_add_staff_confirm(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    tguser = update_or_create_user(update.effective_user)
    if not tguser.is_admin:
        query.message.reply_text("❌ 你不是管理员，无权使用此功能")
        return ConversationHandler.END

    parsed = context.user_data.get("admin_add_staff_data")
    photos = context.user_data.get("admin_add_staff_photos", [])

    if not parsed:
        query.message.reply_text("❌ 没有可创建的数据，请重新开始流程。")
        return ConversationHandler.END

    # 创建 Place
    place, _ = Place.objects.get_or_create(name=parsed["place_name"])

    # 创建 Staff
    staff, created_staff = Staff.objects.get_or_create(
        place=place,
        nickname=parsed["nickname"],
        defaults={"is_active": True}
    )

    # 创建 Submission
    submission = Submission.objects.create(
        staff=staff,
        nickname=parsed["nickname"],
        birth_year=parsed["birth_year"],
        bust_size=parsed["bust_size"],
        bust_info=parsed["bust_info"],
        attractiveness=parsed["attractiveness"],
        extra_info=parsed["extra_info"],
        status="approved",
    )

    # 保存照片（自动审核通过）
    for file_id in photos:
        tg_file = context.bot.get_file(file_id)
        file_bytes = tg_file.download_as_bytearray()

        SubmissionPhoto.objects.create(
            submission=submission,
            image=ContentFile(file_bytes, name=f"{tg_file.file_id}.jpg"),
            status="approved",
        )

    msg = (
        f"✅ 技师已创建：{place.name} - {staff.nickname}"
        if created_staff else
        f"🔄 技师已存在，已更新档案：{place.name} - {staff.nickname}"
    )

    query.message.edit_text(msg, reply_markup=append_back_button(None))

    context.user_data.clear()
    return ConversationHandler.END


# ============================
# 🔥 7. 管理员取消预览
# ============================
def admin_add_staff_cancel_preview(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    query.message.edit_text("❌ 已取消创建技师。", reply_markup=append_back_button(None))
    context.user_data.clear()
    return ConversationHandler.END


# ============================
# 🔥 8. 注册 handlers（ConversationHandler）
# ============================
def register_admin_add_staff_handlers(dp):

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_add_staff_start, pattern=r"^staff_admin:create$"),
        ],
        states={
            TYPING: [
                MessageHandler(
                    Filters.text & ~Filters.regex(r"^/cancel"),
                    admin_add_staff_receive
                ),
            ],
            UPLOADING_PHOTOS: [
                MessageHandler(Filters.photo, admin_add_staff_receive_photo),
                CallbackQueryHandler(admin_add_staff_skip_photos, pattern=r"^staff_admin:skip_photos$"),
            ],
            CONFIRMING: [
                CallbackQueryHandler(admin_add_staff_confirm, pattern=r"^staff_admin:confirm$"),
                CallbackQueryHandler(admin_add_staff_cancel_preview, pattern=r"^staff_admin:cancel_preview$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin_add_staff_cancel),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )

    dp.add_handler(conv)
