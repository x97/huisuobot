# Telethon 账号自动切换装饰器文档

## 概述

`@TelethonAccountManager.with_account_switching` 是一个高级装饰器，专为处理 Telegram API 限制和账号故障而设计。它能够自动在多个 Telethon 账号之间切换，确保任务的持续执行。

## 核心功能

### 1. 自动账号切换
- 当当前账号遇到限制或故障时，自动切换到下一个可用账号
- 支持配置最大重试次数，避免无限循环

### 2. 智能异常处理
- **账号级异常**：触发账号切换（FloodWaitError, ChannelPrivateError 等）
- **业务级异常**：记录日志但不触发切换（用户不存在、数据验证失败等）
- **网络异常**：可配置重试机制

### 3. 状态管理
- 自动标记故障账号状态（limited, banned, error）
- 动态排除已失败账号，避免重复使用

### 4. 资源管理
- 自动创建和销毁 Telethon 客户端
- 确保连接正确关闭，避免资源泄漏

## 使用方法

### 基本用法

```python
from telethon_account.telethon_manager import default_manager as telethon_manager

@telethon_manager.with_account_switching(max_retries=3)
async def my_telegram_task(client=None, account=None, *args, **kwargs):
    """
    被装饰的函数必须接受 client 和 account 参数
    装饰器会自动注入这些参数
    """
    # 使用 client 执行 Telethon 操作
    async with client:
        entity = await client.get_entity('username')
        await client.send_message(entity, "Hello!")
    
    # 可以访问账号信息
    logger.info(f"当前使用账号: {account.phone_number}")
    
    return "任务完成"
```

### 完整示例

```python
@telethon_manager.with_account_switching(max_retries=5)
async def scrape_channel_messages(channel_username: str, client=None, account=None, since_date=None):
    """
    抓取频道消息的示例任务
    """
    logger.info(f"🎯 开始抓取频道 {channel_username}，使用账号: {account.phone_number}")
    
    try:
        # 获取频道实体
        channel = await client.get_entity(channel_username)
        
        # 抓取消息
        messages = []
        async for message in client.iter_messages(channel, limit=100):
            if since_date and message.date < since_date:
                break
            messages.append({
                'id': message.id,
                'text': message.text,
                'date': message.date
            })
        
        logger.info(f"✅ 成功抓取 {len(messages)} 条消息")
        return messages
        
    except Exception as e:
        logger.error(f"❌ 抓取过程发生错误: {e}")
        # 业务异常不需要重新抛出，装饰器会处理账号级异常
        return []
```

### 在 Django Q 任务中使用

```python
# tasks.py
from django_q.tasks import async_task

def start_scraping_task(channel_username: str):
    """启动抓取任务的入口函数"""
    async_task(
        'myapp.tasks.scrape_channel_messages_task',  # 被装饰的异步函数
        channel_username,
        hook='myapp.tasks.scraping_complete_handler'  # 完成后的回调
    )

# 实际执行的任务函数
@telethon_manager.with_account_switching(max_retries=3)
async def scrape_channel_messages_task(channel_username: str, client=None, account=None):
    """Django Q 任务函数"""
    return await scrape_channel_messages(channel_username, client, account)
```

## 参数说明

### 装饰器参数
- `max_retries` (int): 最大重试次数，默认 3 次

### 函数参数（由装饰器注入）
- `client`: Telethon 客户端实例，已连接并准备好使用
- `account`: 当前使用的 TelethonAccount 数据库对象

## 异常处理策略

### 触发账号切换的异常
| 异常类型 | 描述 | 处理方式 |
|---------|------|----------|
| `FloodWaitError` | 请求过于频繁 | 标记为受限，等待后切换 |
| `PeerFloodError` | 对端洪水限制 | 立即切换账号 |
| `ChannelPrivateError` | 频道私有或无权限 | 立即切换账号 |
| `UserBannedInChannelError` | 在频道中被封禁 | 标记为封禁，切换账号 |
| `AuthKeyError` | 认证密钥错误 | 标记为错误，切换账号 |
| `SessionRevokedError` | 会话已撤销 | 标记为错误，切换账号 |

### 不触发切换的异常
- `ValueError`, `TypeError` 等业务逻辑错误
- 数据库操作异常
- 数据验证失败
- 网络暂时性问题（可配置重试）

## 最佳实践

### 1. 正确的函数签名
```python
# ✅ 正确：接受 client 和 account 参数
@telethon_manager.with_account_switching(max_retries=3)
async def good_example(client=None, account=None, custom_arg1=None):
    pass

# ❌ 错误：缺少必要参数
@telethon_manager.with_account_switching(max_retries=3)
async def bad_example(custom_arg1=None):
    # 会报错：缺少 client 和 account 参数
    pass
```

### 2. 异常处理策略
```python
@telethon_manager.with_account_switching(max_retries=3)
async def smart_task(target: str, client=None, account=None):
    try:
        # 让账号级异常自然传播到装饰器
        entity = await client.get_entity(target)
        
        # 业务逻辑...
        
    except (ChannelPrivateError, FloodWaitError) as e:
        # ⚠️ 不要在这里捕获账号级异常！
        # 让它们传播到装饰器处理
        raise
        
    except Exception as e:
        # 只处理业务异常
        logger.error(f"业务逻辑错误: {e}")
        return None
```

### 3. 资源管理
```python
@telethon_manager.with_account_switching(max_retries=3)
async def resource_safe_task(client=None, account=None):
    # 装饰器会自动管理 client 的连接
    # 不需要手动调用 client.connect() 或 client.disconnect()
    
    async with client:
        # 使用 with 语句确保操作在会话内完成
        result = await client.get_me()
    
    # 连接会自动关闭
    return result
```

## 配置建议

### 重试次数配置
```python
# 对于重要任务，增加重试次数
@telethon_manager.with_account_switching(max_retries=5)
async def important_task(client=None, account=None):
    pass

# 对于快速失败的任务，减少重试次数  
@telethon_manager.with_account_switching(max_retries=1)
async def quick_task(client=None, account=None):
    pass
```

### 数据库配置
确保 `TelethonAccount` 模型包含以下字段：
- `phone_number`: 手机号
- `status`: 账号状态（active, limited, banned, error）
- `api_id`, `api_hash`: API 凭证
- `session_string`: 会话数据

## 故障排除

### 常见问题

1. **装饰器不切换账号**
   - 检查是否在内层捕获了账号级异常
   - 确认异常类型在装饰器的处理列表中

2. **客户端连接问题**
   - 确保账号的 session_string 有效
   - 检查 API ID 和 Hash 配置

3. **性能问题**
   - 减少不必要的账号切换
   - 合理设置 max_retries 参数

### 调试模式
```python
# 启用详细日志
import logging
logging.getLogger('telethon_account').setLevel(logging.DEBUG)

@telethon_manager.with_account_switching(max_retries=2)
async def debug_task(client=None, account=None):
    logger.debug(f"使用账号: {account.phone_number}")
    # 任务逻辑...
```

## 总结

这个装饰器提供了强大的账号管理和故障转移能力，让开发者能够专注于业务逻辑，而不必担心 Telegram API 的限制和账号管理问题。正确使用时，可以显著提高应用的稳定性和可靠性。