import re
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    Filters,
    ConversationHandler,
)

from common.callbacks import parse_cb
from common.keyboards import append_back_button
from tgusers.services import update_or_create_user
from collect.models import Campaign, Submission, SubmissionPhoto
from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)

REWARD_PREFIX = "reward"

# ============================
# 🔥 ConversationHandler 状态
# ============================
SUBMITTING_TEXT = 1
SUBMITTING_PHOTOS = 2
CONFIRMING = 3

# ============================
# 🔥 模板字段映射
# ============================
TEMPLATE_FIELDS = {
    "技师号码": "nickname",
    "出生年份": "birth_year",
    "胸围大小": "bust_size",
    "胸围信息": "bust_info",
    "颜值信息": "attractiveness",
    "其他信息": "extra_info",
}

# ============================
# 🔥 用户点击“📝 我要提交”
# ============================
def reward_submit_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    prefix, action, raw_id = parse_cb(query.data)
    if isinstance(raw_id, list):
        raw_id = raw_id[0]

    campaign_id = int(raw_id)
    context.user_data["reward_submit_campaign_id"] = campaign_id

    template = (
        "请按照以下格式填写悬赏信息：\n\n"
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
    return SUBMITTING_TEXT


# ============================
# 🔥 私聊入口：/start reward_<id>
# ============================
def reward_submit_start_private(update: Update, context: CallbackContext):
    message = update.message
    if not message or not message.text:
        return ConversationHandler.END

    text = message.text.strip()
    if not text.startswith("/start reward_"):
        return ConversationHandler.END

    try:
        campaign_id = int(text.replace("/start reward_", "").strip())
    except Exception:
        message.reply_text("链接格式不正确，请重新点击频道中的提交按钮。")
        return ConversationHandler.END

    context.user_data["reward_submit_campaign_id"] = campaign_id

    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        message.reply_text("该悬赏任务不存在或已失效。")
        return ConversationHandler.END

    template = (
        "```text\n"
        "【技师号码】: \n"
        "【出生年份】: \n"
        "【胸围大小】: \n"
        "【胸围信息】: \n"
        "【颜值信息】: \n"
        "【其他信息】: \n"
        "```"
    )

    message.reply_text(
        f"📢 你正在提交悬赏信息：\n\n"
        f"🎯 标题：{campaign.title}\n"
        f"📄 详情：{campaign.description}\n\n"
        f"请按照以下模板填写并发送给我：\n\n"
        f"{template}\n\n"
        f"如需取消，请发送 /cancel",
        parse_mode="Markdown"
    )

    return SUBMITTING_TEXT


# ============================
# 🔥 用户主动取消（/cancel）
# ============================
def reward_submit_cancel(update: Update, context: CallbackContext):
    context.user_data.pop("reward_submit_campaign_id", None)
    context.user_data.pop("reward_submit_submission_id", None)

    update.message.reply_text(
        "已取消悬赏提交。",
        reply_markup=append_back_button(None)
    )
    context.user_data.clear()
    return ConversationHandler.END


# ============================
# 🔥 用户填写模板 → 解析并保存
# ============================

def reward_submit_receive_text(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return SUBMITTING_TEXT

    text = update.message.text.strip()
    campaign_id = context.user_data.get("reward_submit_campaign_id")
    if not campaign_id:
        return SUBMITTING_TEXT

    missing_labels = [label for label in TEMPLATE_FIELDS if f"【{label}】" not in text]
    if missing_labels:
        update.message.reply_text(
            "⚠️ 你发送的内容不符合模板格式，请复制模板并填写后再发送。\n\n"
            "如需取消，请发送 /cancel"
        )
        return SUBMITTING_TEXT

    parsed = {}
    for label, field in TEMPLATE_FIELDS.items():
        pattern = rf"【{label}】\s*:?\s*([^\n]*)"
        match = re.search(pattern, text)
        parsed[field] = match.group(1).strip() if match else ""

    # 这里只保存草稿，不落库
    context.user_data["reward_draft"] = {
        "campaign_id": campaign_id,
        "parsed": parsed,
        "photo_file_ids": [],
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 不上传照片，直接提交", callback_data="reward:skip_photos")]
    ])

    update.message.reply_text(
        "📸 你可以继续上传 1～5 张照片（可选）。\n"
        "如需取消，请发送 /cancel",
        reply_markup=keyboard
    )

    return SUBMITTING_PHOTOS


# ============================
# 🔥 用户上传照片
# ============================

def reward_submit_receive_photo(update: Update, context: CallbackContext):
    draft = context.user_data.get("reward_draft")
    if not draft:
        return SUBMITTING_PHOTOS

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        draft["photo_file_ids"].append(file_id)
        update.message.reply_text(
            f"📸 已收到照片，目前共 {len(draft['photo_file_ids'])} 张。\n"
            "继续发送照片，或发送 /done 进入预览确认。"
        )

    return SUBMITTING_PHOTOS



# ============================
# 🔥 用户完成提交（/done）
# ============================
def reward_submit_skip_photos(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    return _show_preview(query.message, context)


def reward_submit_done(update: Update, context: CallbackContext):
    # 这里来自 /done 命令
    return _show_preview(update.message, context)


def _show_preview(message, context: CallbackContext):
    draft = context.user_data.get("reward_draft")
    if not draft:
        message.reply_text("当前没有正在提交的内容。")
        return ConversationHandler.END

    parsed = draft["parsed"]
    photo_count = len(draft["photo_file_ids"])

    preview_text = (
        "请确认以下内容是否正确：\n\n"
        f"【技师号码】{parsed['nickname']}\n"
        f"【出生年份】{parsed['birth_year']}\n"
        f"【胸围大小】{parsed['bust_size']}\n"
        f"【胸围信息】{parsed['bust_info']}\n"
        f"【颜值信息】{parsed['attractiveness']}\n"
        f"【其他信息】{parsed['extra_info']}\n\n"
        f"📸 照片数量：{photo_count}\n\n"
        "如果确认无误，请点击下方按钮提交。"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 确认提交", callback_data="reward:confirm_submit")],
        [InlineKeyboardButton("🔁 重新填写", callback_data="reward:restart")],
    ])

    message.reply_text(preview_text, reply_markup=keyboard)
    return CONFIRMING


def reward_submit_confirm(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    draft = context.user_data.get("reward_draft")
    if not draft:
        query.edit_message_text("当前没有可提交的内容。")
        return ConversationHandler.END

    campaign = Campaign.objects.get(id=draft["campaign_id"])
    tg_user = update_or_create_user(query.from_user)
    parsed = draft["parsed"]

    # 1) 创建 Submission
    submission = Submission.objects.create(
        campaign=campaign,
        reporter=tg_user,
        nickname=parsed["nickname"],
        birth_year=parsed["birth_year"],
        bust_size=parsed["bust_size"],
        bust_info=parsed["bust_info"],
        attractiveness=parsed["attractiveness"],
        extra_info=parsed["extra_info"],
        status="pending",
    )

    # 2) 保存图片
    for file_id in draft["photo_file_ids"]:
        tg_file = context.bot.get_file(file_id)
        file_bytes = tg_file.download_as_bytearray()
        SubmissionPhoto.objects.create(
            submission=submission,
            image=ContentFile(file_bytes, name=f"{tg_file.file_id}.jpg")
        )

    # 3) 清理上下文
    context.user_data.pop("reward_draft", None)
    context.user_data.pop("reward_submit_campaign_id", None)

    # 4) 更新频道按钮
    try:
        notify = campaign.notifications.first()
        if notify:
            total = Submission.objects.filter(campaign=campaign).count()

            bot_username = context.bot.username
            deep_link = f"https://t.me/{bot_username}?start=reward_{campaign.id}"

            new_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"📝 我要提交 ({total}人已提交)",
                        url=deep_link
                    )
                ]
            ])

            context.bot.edit_message_reply_markup(
                chat_id=notify.notify_channel_id,
                message_id=notify.message_id,
                reply_markup=new_keyboard
            )
    except Exception as e:
        logger.error(f"更新频道按钮失败: {e}")

    # 5) 提示用户
    query.edit_message_text(
        "✅ 已收到你的提交，等待管理员审核。",
        reply_markup=append_back_button(None)
    )

    return ConversationHandler.END


def reward_submit_restart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    context.user_data.pop("reward_draft", None)
    context.user_data.pop("reward_submit_campaign_id", None)

    query.edit_message_text("本次提交已取消，如需重新提交，请再次点击悬赏入口。")
    return ConversationHandler.END


# ============================
# 🔥 注册 handlers（ConversationHandler）
# ============================
def register_reward_submit_handlers(dp):

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r"^/start reward_\d+$"), reward_submit_start_private),
            CallbackQueryHandler(reward_submit_start, pattern=r"^reward:submit:\d+$"),
        ],

        states={
            SUBMITTING_TEXT: [
                # 避免 /cancel 被当成普通文本
                MessageHandler(Filters.text & ~Filters.regex(r"^/cancel"), reward_submit_receive_text),
            ],

            SUBMITTING_PHOTOS: [
                MessageHandler(Filters.photo, reward_submit_receive_photo),
                CommandHandler("done", reward_submit_done),
                CallbackQueryHandler(reward_submit_skip_photos, pattern=r"^reward:skip_photos$"),
            ],

            CONFIRMING: [
                CallbackQueryHandler(reward_submit_confirm, pattern=r"^reward:confirm_submit$"),
                CallbackQueryHandler(reward_submit_restart, pattern=r"^reward:restart$"),
            ],
        },

        fallbacks=[
            CommandHandler("cancel", reward_submit_cancel),
        ],

        per_user=True,
        per_chat=True,
        allow_reentry=True,   # ⭐ 必须加
    )

    dp.add_handler(conv)

