好的，我来帮你写一份完整的 **README.md** 文档，包含项目说明、架构逻辑的 ASCII 图、使用方法以及测试案例。这样你可以直接放到仓库里，团队成员或未来的自己都能快速理解。

---

# 📖 Carousel Bot README

## 1. 项目简介
本项目是一个基于 **Django + Django‑Q + python‑telegram‑bot** 的轮播消息系统。  
它支持：
- 在 **Admin** 中配置轮播任务（群组、数据源、分页大小、是否置顶等）
- 自动调度消息发送（通过 Django‑Q 定时任务）
- 支持 **分页按钮**（上一页 / 下一页）
- 支持 **自定义按钮**（URL 跳转 / Callback 回调）
- 支持 **同步入口**（给 Django‑Q 调度用）和 **异步入口**（给 Bot handler 用）

---

## 2. 系统架构逻辑

```
+-------------------+        +-------------------+        +-------------------+
|   Django Admin    |        |   Django-Q Worker |        |   Telegram Server |
|  配置 Carousel    |        | 调度 execute_...  |        |   接收并显示消息  |
+-------------------+        +-------------------+        +-------------------+
          |                           |                           |
          v                           v                           v
+-------------------+        +-------------------+        +-------------------+
|  CarouselConfig   | -----> |   tasks.py        | -----> |   CarouselBot     |
|  (数据库模型)     |        | execute_carousel  |        | send_message_sync |
+-------------------+        | execute_carousel_async     | send_message_async|
                             +-------------------+        +-------------------+
                                      |
                                      v
                             +-------------------+
                             | GenericCarousel   |
                             |  Manager          |
                             | 生成分页按钮等逻辑 |
                             +-------------------+
```

---

## 3. 模块说明

- **models.py**
  - `CarouselConfig`：轮播配置（群组、数据源、分页大小等）
  - `CarouselButton`：自定义按钮（URL / Callback）

- **carousel_bot.py**
  - `CarouselBot`：封装 Telegram Bot 的发送逻辑
    - `send_carousel_message_sync`：同步版本，给 Django‑Q 用
    - `send_carousel_message`：异步版本，给 Bot handler 用

- **tasks.py**
  - `execute_carousel`：同步入口，Django‑Q 调度调用
  - `execute_carousel_async`：异步入口，Bot handler 调用
  - 自动调度下次任务（分页或重试）

- **signals.py**
  - 在 Admin 保存 `CarouselConfig` 时，自动注册一次性任务到 Django‑Q

---

## 4. 使用方法

### 4.1 安装依赖
```bash
pip install django django-q python-telegram-bot
```

### 4.2 配置 Django‑Q
在 `settings.py` 中添加：
```python
INSTALLED_APPS = [
    ...,
    "django_q",
    "tgfunc_carousel",
]

Q_CLUSTER = {
    "name": "DjangoQ",
    "workers": 4,
    "timeout": 90,
    "retry": 120,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}
```

启动 worker：
```bash
python manage.py qcluster
```

### 4.3 配置 Telegram Bot Token
在 `settings.py` 中添加：
```python
TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
```

### 4.4 在 Admin 添加轮播
1. 打开 Django Admin
2. 新建一个 `CarouselConfig`
   - 填写群组 ID (`chat_id`)
   - 填写数据源函数路径 (`data_fetcher`)
   - 设置分页大小、是否置顶等
   - 勾选 `is_active`
3. 保存后，signals 会自动注册一次性任务到 Django‑Q

---

## 5. 测试案例

### 5.1 测试同步入口（Django‑Q）
```python
from tgfunc_carousel.tasks import execute_carousel
execute_carousel(1)
```
预期：在群组里发送一条轮播消息，并注册下次任务。

---

### 5.2 测试异步入口（Bot handler）
```python
import asyncio
from tgfunc_carousel.tasks import execute_carousel_async

asyncio.run(execute_carousel_async(1))
```
预期：在群组里发送一条轮播消息，并注册下次任务。

---

### 5.3 测试按钮
在 Admin 添加一个 `CarouselButton`：
- 文本：`查看官网`
- 类型：`url`
- URL：`https://example.com`

预期：轮播消息里出现一个按钮，点击后跳转到官网。

---

### 5.4 测试回调按钮
在 Admin 添加一个 `CarouselButton`：
- 文本：`收藏`
- 类型：`callback`
- Callback data：`favorite_item_123`

在 Bot 初始化时注册 handler：
```python
    #注册带按钮的轮播
from tgfunc_carousel.carousel_registry import registry
registry.register_handlers(dispatcher)
```

预期：点击按钮后，Bot 回复「已收藏！」。

---

## 6. 总结
- **Admin** → 配置轮播任务和按钮  
- **Django‑Q** → 调度同步入口，负责定时发送  
- **CarouselBot** → 封装发送逻辑，支持同步/异步  
- **GenericCarouselManager** → 生成分页按钮和轮播逻辑  
- **测试案例** → 验证同步入口、异步入口、按钮功能  

---

嘉熙，我可以帮你把这个 README 直接生成成 Markdown 文件，你只要复制到项目根目录就能用了。要不要我再帮你画一个更详细的 **按钮交互流程图**（比如点击按钮 → CallbackQuery → Handler → 数据库更新）？