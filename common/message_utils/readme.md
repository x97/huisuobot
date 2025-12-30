好的，嘉熙，我帮你写一个完整的 **README 文档**，结合你之前问到的点（消息发送、按钮、置顶、预览、返回 `message_id`、`InlineKeyboardMarkup`、`parse_mode` 等），让这个库更像一个可安装的 Django 插件。  

---

# 📖 Telegram Message Utils

一个基于 **Django + python-telegram-bot==13.7 + django-q==1.3.9** 的工具库，用于发送纯文本消息到 Telegram 群组或个人/多人聊天。支持按钮、置顶、网页预览控制、消息格式化等功能。

---

## ✨ 特性
- 发送 **纯文本消息**（支持 HTML / Markdown 格式化）
- 支持 **InlineKeyboardMarkup** 按钮（可直接传对象或 dict 列表）
- 可选 **置顶消息**
- 可选 **禁用网页预览**
- 返回完整的 **telegram.Message** 对象（可获取 `message_id` 等属性）
- 与 **django-q** 集成，支持异步消息发送

---

## 📦 安装与配置

1. 安装依赖：
   ```bash
   pip install python-telegram-bot==13.7 django-q==1.3.9
   ```

2. 在 `settings.py` 中配置：
   ```python
   TELEGRAM_BOT_TOKEN = "your-bot-token"
   ```

3. 在 Django 项目中创建一个 app，例如 `telegram_utils`。

---

## 🏗 目录结构示例
```
telegram_utils/
├── __init__.py
├── sender.py        # 消息发送核心逻辑
├── tasks.py         # 与 django-q 集成的任务封装
└── README.md        # 使用说明
```

---

## 📤 使用方法

### 1. 直接发送消息
```python
from telegram_utils.sender import send_text_message

msg = send_text_message(
    chat_id=-10123456789,  # 群组ID或用户ID
    text="这是一个测试消息 <b>加粗</b>",
    buttons=[[{"text": "官网", "url": "https://example.com"}]],
    disable_web_page_preview=False,
    pin_message=True,
    parse_mode="HTML",  # 可选: "MarkdownV2"
)

print(msg.message_id)  # 获取消息ID

返回。telegram.Message 对象，可获取 message_id、chat、date、text 等属性

这个对象包含了很多属性，常用的有：

    message_id → 消息的唯一 ID（你需要的）

    chat → telegram.Chat 对象，包含群/用户信息

    date → 消息发送时间（UTC）

    text → 消息正文

    entities → 文本中的格式化实体（比如链接、粗体）

    reply_markup → 如果有按钮，返回的 InlineKeyboardMarkup 或 ReplyKeyboardMarkup

```

### 2. 异步发送消息（推荐）
```python
from telegram_utils.tasks import queue_message

queue_message(
    chat_id=-100123456789,
    text="异步发送测试消息",
    buttons=None,  # 可以传 None
    disable_web_page_preview=True,
    pin_message=False,
    parse_mode="MarkdownV2",
)
```

---

## 🧩 函数说明

### `send_text_message`
- **参数**
  - `chat_id`: 群组或用户 ID
  - `text`: 消息正文
  - `buttons`: 可选，支持 `InlineKeyboardMarkup` 或 `list[list[dict]]`
  - `disable_web_page_preview`: 是否禁用网页预览
  - `pin_message`: 是否置顶消息
  - `parse_mode`: 消息解析模式，支持 `"HTML"` / `"MarkdownV2"`
- **返回**
  - `telegram.Message` 对象，可获取 `message_id`、`chat`、`date`、`text` 等属性

### `queue_message`
- 封装 `django-q` 的异步任务调用
- 自动调用 `send_text_message`
- 支持任务 hook 打印成功/失败日志

---

## 🔑 注意事项
- **按钮传入**：如果传 `None`，不会报错；如果传 `InlineKeyboardMarkup`，直接使用；如果传 `list[list[dict]]`，会自动转换。
- **返回值**：始终返回 `telegram.Message`，推荐使用 `msg.message_id` 做后续操作（编辑、删除、转发）。
- **parse_mode**：推荐使用 `"HTML"` 或 `"MarkdownV2"`，旧版 `"Markdown"` 已不再维护。
- **生命周期管理**：未来可扩展 `edit_message`、`delete_message` 等方法。

---

## 🚀 示例场景
- **群公告**：发送置顶消息，禁用网页预览，保证信息突出。
- **客服机器人**：发送带按钮的消息，按钮跳转到外部链接或触发回调。
- **定时任务**：结合 `django-q`，每天定时推送消息到群组。

---

嘉熙，这个 README 已经覆盖了你问到的所有点：  
- 返回对象类型和属性  
- `buttons=None` 的处理  
- `InlineKeyboardMarkup` 的支持  
- `parse_mode` 的选择  

