# 核心是发布抽奖
import datetime
from datetime import timedelta

from django.utils import timezone
from django.conf import settings
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackQueryHandler
)

from mygroups.models import GroupInfo
from tgusers.models import TelegramUser
from tgusers.services import update_or_create_user
from common.utils import end_all_conversations
from lottery.services import send_lottery_to_group, add_lottery_draw_job

from .models import Lottery, Prize, LotteryParticipant
from .models import LotteryWinner  #

# 定义对话状态
TITLE, CHAT_LINK, END_TIME, REQUIRED_POINTS, PRIZE_NAME, PRIZE_QUANTITY, DESCRIPTION, CONFIRM = range(40,48)
# 定义“结束添加”按钮
END_ADDITION_BUTTON = "🔚 结束添加奖品"

def admin_check(update, context):
    """检查用户是否为管理员"""
    user = update_or_create_user(update.effective_user)
    return user.is_admin


def get_chat_id_from_link(context, chat_link):
    """
    从群组链接解析 chat_id
    支持格式：https://t.me/joinchat/xxx 或 https://t.me/群组用户名
    """
    # 提取核心链接（去除多余参数）
    import re
    # 匹配两种链接格式：joinchat 或 公开群组用户名
    pattern = r'(https?://t\.me/)(joinchat/)?([a-zA-Z0-9_-]+)'
    match = re.search(pattern, chat_link)
    if not match:
        return None

    invite_path = match.group(3)
    # 构建标准邀请链接（joinchat 格式）

    print(invite_path)
    try:
        # 调用 Telegram API 获取群组信息（需要 bot 已加入该群组）
        chat = context.bot.get_chat(f"@{invite_path}")
        return chat.id  # 返回 chat_id（整数）
    except Exception as e:
        print(f"解析群组链接失败：{e}")
        return None


# 步骤1：启动抽奖创建（由「发布抽奖」按钮触发）
def start_create_lottery(update, context):
    """触发创建流程，仅管理员可进入，直接返回第一步 TITLE 状态"""
    # 验证管理员
    if not admin_check(update, context):
        if update.message:
            update.message.reply_text("抱歉，只有管理员才能创建抽奖～")
        else:
            query = update.callback_query
            query.answer()
            query.edit_message_text("抱歉，只有管理员才能创建抽奖～")
        return ConversationHandler.END

    # 初始化 user_data 存储抽奖数据（避免键不存在报错）
    context.user_data.clear()
    context.user_data['lottery'] = {}
    context.user_data['prizes'] = []

    # 根据触发方式回复（CallbackQuery→编辑原消息，Command→直接回复）
    if update.message:
        # 命令触发（如 /create_lottery）
        update.message.reply_text(
            "/cancel 命令返回首页 \n"
            "📢 开始创建抽奖（共7步）\n第一步：请输入抽奖标题",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # 按钮触发（Inline 按钮点击）
        query = update.callback_query
        query.answer()
        query.edit_message_text("/cancel 命令返回首页 \n"
                                "📢 开始创建抽奖（共7步）\n第一步：请输入抽奖标题\n\n ")

    return TITLE  # 进入第一步：输入标题


def handle_title(update, context):
    """处理用户输入的标题，进入新增步骤：输入群组链接"""
    title = update.message.text.strip()
    if not title:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "标题不能为空，请重新输入抽奖标题：")
        return TITLE

    # 保存标题到 user_data
    context.user_data['lottery']['title'] = title
    # 进入新增步骤：提示输入群组链接
    update.message.reply_text(
        "/cancel 命令返回首页 \n"
        "✅ 标题已保存！\n第二步：请输入抽奖要发布的群组链接\n"
        "（支持格式： https://t.me/群组用户名）\n ",
        reply_markup=ReplyKeyboardRemove()
    )
    return CHAT_LINK  # 进入新增的 CHAT_LINK 状态
def handle_chat_link(update, context):
    """处理用户输入的群组链接，解析 chat_id 后进入开奖时间输入"""
    chat_link = update.message.text.strip()
    if not chat_link.startswith("https://t.me/"):
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "链接格式错误！请输入以 https://t.me/ 开头的群组链接：")

        return CHAT_LINK

    # 解析 chat_id
    chat_id = get_chat_id_from_link(context, chat_link)

    if not chat_id or chat_id not in GroupInfo.ALLOWED_GROUP_IDS():
        update.message.reply_text(
            "/cancel 命令返回首页 \n"
            "❌链接有问题哦\n"
            "✅请确认："
            "1. 链接正确\n"
            "2. 机器人已被邀请进该群组\n"
            "3. 本机器人只在规定群里发布抽奖\n"
            "重新输入群组链接："
        )
        return CHAT_LINK

    # 保存 chat_id 到 user_data（用于后续发布抽奖）
    context.user_data['lottery']['chat_id'] = chat_id
    # 进入原有第二步：提示输入开奖时间
    update.message.reply_text(
        f"/cancel 命令返回首页 \n"
        f"✅ 群组已验证！\n第三步：请输入开奖时间\n"
        "（格式：YYYY-MM-DD HH:MM，\n"
        "例：2025-09-01 20:00）\n " ,
        reply_markup=ReplyKeyboardRemove()
    )
    return END_TIME  # 跳转至原有 END_TIME 步骤



# 步骤2→步骤3：处理开奖时间，进入所需积分输入
def handle_end_time(update, context):
    """验证开奖时间格式，进入第三步：输入参与积分"""
    time_text = update.message.text.strip()
    try:
        # 解析时间（必须严格匹配 YYYY-MM-DD HH:MM）
        end_time = datetime.datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        # 校验时间不能早于当前时间
        if end_time < datetime.datetime.now():
            update.message.reply_text("/cancel 命令返回首页 \n"
                                      "开奖时间不能早于当前时间，请重新输入：")
            return END_TIME
    except ValueError:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "时间格式错误！请按 YYYY-MM-DD HH:MM 重新输入：")
        return END_TIME

    # 保存开奖时间
    context.user_data['lottery']['end_time'] = end_time
    # 进入第三步：提示输入积分
    update.message.reply_text(
        "✅ 开奖时间已保存！\n第三步：请输入参与本次抽奖所需的积分（正整数）",
        reply_markup=ReplyKeyboardRemove()
    )
    return REQUIRED_POINTS

# 步骤3→步骤4：处理参与积分，进入奖品添加
def handle_required_points(update, context):
    """验证积分格式，进入第四步：添加奖品（名称+数量）"""
    points_text = update.message.text.strip()
    try:
        points = int(points_text)
        if points <= 0:
            raise ValueError("积分必须为正整数")
    except ValueError:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "积分格式错误！请输入正整数：")
        return REQUIRED_POINTS

    # 保存积分
    context.user_data['lottery']['required_points'] = points
    # 进入第四步：提示添加奖品（第一个奖品）
    update.message.reply_text(
        f"/cancel 命令返回首页 \n"
        f"✅ 参与积分已保存（{points} XP）！\n第四步：添加奖品\n请输入第一个奖品的名称",
        reply_markup=ReplyKeyboardRemove()
    )
    return PRIZE_NAME

# 步骤4-1：处理奖品名称，进入数量输入
def handle_prize_name(update, context):
    """保存奖品名称，进入奖品数量输入"""
    prize_name = update.message.text.strip()
    if not prize_name:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "奖品名称不能为空，请重新输入：")
        return PRIZE_NAME

    # 保存奖品名称到临时变量（等待数量输入）
    context.user_data['temp_prize_name'] = prize_name
    update.message.reply_text(f"/cancel 命令返回首页 \n"
                              f"✅ 奖品名称已保存（{prize_name}）！\n请输入该奖品的数量（正整数）")
    return PRIZE_QUANTITY

# 步骤4-2：处理奖品数量，循环添加或结束
def handle_prize_quantity(update, context):
    """保存奖品数量，提示继续添加或结束（使用行内按钮）"""
    try:
        quantity = int(update.message.text.strip())
        if quantity <= 0:
            raise ValueError("数量必须为正整数")
    except ValueError:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "数量格式错误！请输入正整数：")
        return PRIZE_QUANTITY

    # 保存奖品到列表
    prize_name = context.user_data.pop('temp_prize_name')
    context.user_data['prizes'].append({
        'name': prize_name,
        'quantity': quantity
    })

    # 显示“结束添加奖品”行内按钮
    inline_keyboard = [
        [InlineKeyboardButton("🔚 结束添加奖品", callback_data="end_prize_addition")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)

    update.message.reply_text(
        f"/cancel 命令返回首页 \n"
        f"✅ 奖品已添加：{prize_name}（{quantity}份）\n"
        f"当前已添加 {len(context.user_data['prizes'])} 个奖品\n"
        "👉 继续添加请输入新奖品名称，或点击下方按钮结束",
        reply_markup=reply_markup
    )
    return PRIZE_NAME  # 继续等待输入或按钮点击

# 步骤4-3：处理“结束添加奖品”，进入兑奖说明
def handle_end_prize_addition(update, context):
    """点击结束添加，验证至少1个奖品，进入第五步：兑奖说明"""
    if len(context.user_data['prizes']) == 0:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "至少需要添加1个奖品！请输入奖品名称：")
        return PRIZE_NAME

    # 进入第五步：提示输入兑奖说明
    update.message.reply_text(
        f"/cancel 命令返回首页 \n"
        f"✅ 奖品添加完成（共 {len(context.user_data['prizes'])} 个）！\n第五步：请输入兑奖说明（如领取方式、有效期等）",
        reply_markup=ReplyKeyboardRemove()
    )
    return DESCRIPTION

# 步骤5→步骤6：处理兑奖说明，生成预览
def handle_description(update, context):
    """保存兑奖说明，生成抽奖预览（第六步）"""
    description = update.message.text.strip()
    if not description:
        update.message.reply_text("/cancel 命令返回首页 \n"
                                  "兑奖说明不能为空，请重新输入：")
        return DESCRIPTION

    # 保存兑奖说明
    context.user_data['lottery']['description'] = description
    # 构建预览信息
    lottery = context.user_data['lottery']
    prizes = context.user_data['prizes']

    preview_text = f"""
📢 【抽奖预览】📢
━━━━━━━━━━━━━━
标题：{lottery['title']}
参与积分：{lottery['required_points']} XP
开奖时间：{lottery['end_time'].strftime('%Y-%m-%d %H:%M')}

🎁 奖品列表（共 {len(prizes)} 个）
━━━━━━━━━━━━━━
"""
    for i, prize in enumerate(prizes, 1):
        preview_text += f"{i}. {prize['name']} - {prize['quantity']}份\n"

    preview_text += f"""
📝 兑奖说明
━━━━━━━━━━━━━━
{description}

✅ 确认以上信息无误？点击下方按钮发布/取消
    """

    # 预览后显示「确认发布」/「取消」按钮（Inline 样式）
    inline_keyboard = [
        [InlineKeyboardButton("✅ 确认发布", callback_data="lottery_publish")],
        [InlineKeyboardButton("❌ 取消发布", callback_data="lottery_cancel")]
    ]
    update.message.reply_text(
        preview_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard),
        parse_mode='Markdown'
    )
    return CONFIRM  # 进入第七步：确认发布

# 步骤7：确认发布/取消，保存到数据库
def confirm_publish_lottery(update, context):
    """处理发布/取消按钮，保存抽奖到数据库"""
    query = update.callback_query
    if not query:
        if update.message:
            update.message.reply_text("操作异常，请重新尝试。")
        return ConversationHandler.END

    query.answer()

    # 创建返回按钮键盘（提前创建，两种情况都能用）
    keyboard = [[InlineKeyboardButton("🔙 返回抽奖管理", callback_data="lottery_management")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query.data == "lottery_publish":
        try:
            lottery_data = context.user_data['lottery']
            prizes_data = context.user_data['prizes']
            lottery = Lottery.objects.create(
                title=lottery_data['title'],
                description=lottery_data['description'],
                required_points=lottery_data['required_points'],
                end_time=timezone.make_aware(lottery_data['end_time']),
                group_id=lottery_data['chat_id'],  # 保存目标群组ID
                is_active=True
            )
            for prize in prizes_data:
                Prize.objects.create(lottery=lottery, name=prize['name'], quantity=prize['quantity'])

            # 发送抽奖信息到群里
            send_lottery_to_group(context, lottery)
            #添加定时抽奖任务
            add_lottery_draw_job(lottery)

            # 成功：将消息和按钮合并更新
            success_text = f"🎉 抽奖【{lottery.title}】已成功发布！\n所有用户可参与～"
            query.edit_message_text(
                text=success_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            # 失败处理
            query.edit_message_text(text=f"/cancel 命令返回首页 \n"
                                         f"❌ 发布失败：{e}")

    else:
        # 取消发布：将消息和按钮合并更新
        query.edit_message_text(
            text="❌ 抽奖创建已取消，所有信息未保存",
            reply_markup=reply_markup
        )

    # 清空用户会话数据
    context.user_data.clear()

    # 结束对话
    return ConversationHandler.END


# 取消创建流程（任何步骤发送 /cancel 均可触发）
def cancel_create_lottery(update, context):
    """取消抽奖创建，清空数据"""

    """取消对话，并提供返回抽奖管理的按钮"""
    user = update.message.from_user

    # 创建返回按钮
    keyboard = [[InlineKeyboardButton("🔙 返回抽奖管理", callback_data="lottery_management")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        f"操作已取消。",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


def handle_end_prize_callback(update, context):
    """处理“结束添加奖品”按钮的回调"""
    query = update.callback_query
    query.answer()  # 必须调用，否则 Telegram 会显示“等待中”

    # 检查是否至少添加了一个奖品
    if len(context.user_data.get('prizes', [])) == 0:
        query.edit_message_text("❌ 至少需要添加一个奖品！请输入奖品名称：")
        return PRIZE_NAME

    # 结束添加，进入下一步（输入兑奖说明）
    query.edit_message_text(
        f"✅ 奖品添加完成（共 {len(context.user_data['prizes'])} 个）！\n"
        "请输入兑奖说明："
    )
    return DESCRIPTION  # 进入兑奖说明步骤


create_lottery_handler  = ConversationHandler(
        entry_points=[
            # 触发方式1：Inline 按钮（管理员点击「发布抽奖」）
            CallbackQueryHandler(start_create_lottery, pattern="^admin_publish_lottery$"),
            # 触发方式2：命令（/create_lottery，方便测试）
            CommandHandler("create_lottery", start_create_lottery)
        ],
        states={
            # 7步流程对应的状态+处理器
            TITLE: [MessageHandler(Filters.text & ~Filters.command, handle_title)],
            CHAT_LINK: [MessageHandler(Filters.text & ~Filters.command, handle_chat_link)],
            END_TIME: [MessageHandler(Filters.text & ~Filters.command, handle_end_time)],
            REQUIRED_POINTS: [MessageHandler(Filters.text & ~Filters.command, handle_required_points)],
            PRIZE_NAME: [
                MessageHandler(Filters.text & ~Filters.command, handle_prize_name),
                CallbackQueryHandler(handle_end_prize_callback, pattern="^end_prize_addition$")
            ],
            PRIZE_QUANTITY: [MessageHandler(Filters.text & ~Filters.command, handle_prize_quantity)],
            DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, handle_description)],
            CONFIRM: [CallbackQueryHandler(confirm_publish_lottery)]
        },
        fallbacks=[
            # 任何步骤发送 /cancel 均可取消
            CommandHandler('cancel', lambda u, c: end_all_conversations(c)),  # 优化：调用结束函数
            CallbackQueryHandler(lambda u, c: end_all_conversations(c), pattern='^.*$'),  # 捕获其他按钮点击，强制结束
        ],
        allow_reentry=False,  # 防止重复触发
        per_user=True,
        per_chat=True,
    )




def handle_join_lottery(update, context):
    """
    处理用户点击“立即参与”按钮的逻辑。
    支持重复参与，并根据参与次数给出不同提示。
    """
    query = update.callback_query
    query.answer()  # 消除 Telegram 的“正在等待”提示
    chat_id = query.message.chat_id  # 群聊的 chat_id，确保消息发送到当前群

    # 1. 解析 callback_data，获取抽奖 ID
    try:
        # callback_data 的格式是 "join_lottery_123"
        lottery_id = int(query.data.split("_")[-1])
        # 获取当前有效的抽奖
        lottery = Lottery.objects.get(id=lottery_id, is_active=True)
    except (IndexError, ValueError):
        context.bot.send_message(chat_id=chat_id, text="❌ 无效的抽奖链接。")
        return
    except Lottery.DoesNotExist:
        context.bot.send_message(chat_id=chat_id, text="❌ 该抽奖不存在或已结束。")
        return

    # 2. 验证抽奖是否已过期
    now = timezone.now()
    if now > lottery.end_time:
        context.bot.send_message(chat_id=chat_id,text="⏰ 该抽奖已过期，无法参与。")
        return

    # 3. 获取参与用户信息
    user = update_or_create_user(update.effective_user)
    # 表示用户跟机器人有交互
    if user and not user.has_interacted:
        user.has_interacted = True
        user.save()

    # 4. 验证用户积分是否足够
    # 因为这里有的用户头衔高 有抽奖折扣
    required_points = int(lottery.required_points * user.discount)
    if user.total_points < required_points:
        context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ {user.first_name or '' }积分不足！参与本次抽奖需要 {lottery.required_points} 积分，"
            f"您当前剩余 {user.total_points} XP。"
        )
        return

    # 5. 计算用户当前参与次数（用于提示）
    participation_count = LotteryParticipant.objects.filter(
        lottery=lottery,
        user=user
    ).count()

    # 6. 执行参与逻辑
    try:
        # 扣减积分
        user.total_points -= required_points
        user.save()

        # 记录参与信息
        LotteryParticipant.objects.create(
            lottery=lottery,
            user=user
        )

        # 7. 根据参与次数构建回复消息
        new_participation_count = participation_count + 1
        total_participants = LotteryParticipant.objects.filter(lottery=lottery).count()

        if participation_count == 0:
            # 第一次参与
            message = (
                f"🎉 恭喜【{user.first_name or ''} {user.last_name or ''}】成功参与\n"
                f"【{lottery.title}】抽奖活动！\n"
                f"✅ 已扣除 {required_points} 积分，当前剩余 {user.total_points} 积分。\n"
                f"📊 本次抽奖已有 {total_participants} 人次参与。\n"
            )
        else:
            # 重复参与
            message = (
                f"🎉 恭喜【{user.first_name or ''} {user.last_name or '' }】成功参与！\n"
                f"【{lottery.title}】抽奖活动！\n"
                f"✅ 已扣除 {required_points} 积分，当前剩余 {user.total_points} 积分。\n"
                f"✨ 您已参与 {new_participation_count} 次，中奖概率已提升！\n"
                f"📊 本次抽奖已有 {total_participants} 人次参与。\n\n"
            )
        if user.discount < 1:
            message += f"因为你是尊贵的【{user.title}】用户\n 您的抽奖积分已打{user.discount * 10} 折\n"
        # 8. 修改原消息内容，提示参与结果
        context.bot.send_message(chat_id=chat_id,text=message)

    except Exception as e:
        # 异常处理
        context.bot.send_message(chat_id=chat_id,text=f"⚠️ 参与失败，请稍后重试。错误：{str(e)}")
        # 可以在这里添加日志记录
        print(f"用户参与抽奖失败: {user.user_id}, 抽奖ID: {lottery.id}, 错误: {e}")




def my_wins(update: Update, context: CallbackContext):
    """处理 /mywins 命令，查询用户最近一个月的中奖记录"""
    user = update.effective_user
    if not user:
        return

    # 1. 获取或创建用户
    try:
        telegram_user = TelegramUser.objects.get(user_id=user.id)
    except TelegramUser.DoesNotExist:
        update.message.reply_text("你好！你还没有与我进行过任何互动。参与一次抽奖或发送 /start 开始吧！")
        return

    # 2. 计算一个月前的时间点
    one_month_ago = timezone.now() - timedelta(days=30)

    # 3. 查询最近一个月的中奖记录
    # 这里假设你的中奖记录表是 UserWinning，并且有 user, lottery, prize, won_at 这些字段
    winnings = LotteryWinner.objects.filter(
        user=telegram_user,
        created_at__gte=one_month_ago
    ).select_related('lottery', 'prize').order_by('-created_at')

    # 4. 格式化并发送结果
    if winnings.exists():
        message_parts = ["🎉 你最近一个月的中奖记录如下：\n"]
        for win in winnings:
            message_parts.append(
                f"\n⭐️    【{win.lottery.title}】\n"
                f"  🎁 奖品：{win.prize.name}\n"
                f"  📒兑奖说明:\n {win.lottery.description}\n"
                f"  📅 时间：{win.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            )
        message_parts.append("\n恭喜你！可联系管理员兑奖哦！")
        full_message = "".join(message_parts)
        return full_message
    else:
        return "😔 你最近一个月没有中奖记录。\n快去参与更多抽奖活动吧！"




def handle_lottery_query(update: Update, context: CallbackContext):
    """监听群聊中“抽奖”关键词，回复正在进行的抽奖"""
    # 仅处理群聊消息，忽略私聊
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    # 获取群聊信息
    chat_id = update.message.chat.id
    user = update.message.from_user

    # 查询当前正在进行的抽奖（已发布、未开奖、未过期）
    ongoing_lotteries = Lottery.objects.filter(
        is_active=True,
        is_drawn=False,
        end_time__gt=timezone.now(),
        group_id=chat_id
    ).order_by('-created_at')

    # 处理回复内容
    if not ongoing_lotteries.exists():
        update.message.reply_text("🎫 本群当前没有正在进行的抽奖哦～")
        return

    def get_lottery_link(update, link_chat_id, group_message_id):
        chat = update.message.chat
        if chat.username:  # 公开群会有username
            public_link = f"https://t.me/{chat.username}/"
            from urllib.parse import urljoin
            return urljoin(public_link, str(group_message_id))
        #返回私密链接
        return f"https://t.me/c/{link_chat_id}/{group_message_id}"

    # 构建回复文本（支持Markdown格式）
    reply_text = "🎉 本群正在进行的抽奖：\n\n"
    for idx, lottery in enumerate(ongoing_lotteries, 1):
        # 转换群聊ID格式：Telegram群聊ID为负数，链接中需去掉负号（如 -100123456789 → 100123456789）
        link_chat_id = str(chat_id).lstrip('-')
        # 拼接抽奖消息链接
        lottery_link =  get_lottery_link(update, link_chat_id, lottery.group_message_id)

        # 格式化结束时间
        end_time_str = lottery.end_time.strftime('%Y-%m-%d %H:%M')

        # 拼接单条抽奖信息（带跳转链接）
        reply_text += (
            f"{idx}. 【{lottery.title}】\n"
            f"   ⏰ 截止时间：{end_time_str}\n"
            f"   🔗 [点击参与抽奖]({lottery_link})\n\n"
        )

    # 发送回复（启用Markdown解析）
    update.message.reply_text(
        reply_text,
        parse_mode='Markdown',
        disable_web_page_preview=True  # 禁用链接预览，避免刷屏
    )





