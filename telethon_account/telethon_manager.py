import logging
import asyncio
from datetime import datetime, timedelta
from django.utils import timezone
from functools import wraps
from django.db import transaction
from telethon import TelegramClient
from telethon.sessions import StringSession

from telethon.errors import (
    PeerFloodError,
    FloodWaitError,
    UserBannedInChannelError,
    AuthKeyError,
    SessionRevokedError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    ChannelPrivateError
)

from asgiref.sync import sync_to_async

from .models import TelethonAccount

logger = logging.getLogger(__name__)


class TelethonAccountManager:
    """
    增强版 Telethon 账号管理器，支持自动选择账号和失败时自动切换。
    优化了异常处理逻辑，确保临时错误不会误判账号状态。
    """

    # ... (其他静态方法 _create_client, get_available_account, update_account_status, login_account 保持不变) ...

    @staticmethod
    async def _create_client(account: TelethonAccount) -> TelegramClient:
        """根据账号信息创建并返回一个 Telethon 客户端实例。"""
        session = StringSession(account.session_string)
        client = TelegramClient(
            session,
            account.api_id,
            account.api_hash,
            timeout=30
        )
        return client

    @staticmethod
    async def get_available_account() -> TelethonAccount:
        """异步获取可用账号"""
        now = datetime.now(timezone.utc)

        try:
            def _query_account_sync():
                with transaction.atomic():
                    # 优先选择完全空闲的账号
                    account = (TelethonAccount.objects
                               .select_for_update()
                               .filter(
                        status='authorized',
                        limited_until__isnull=True,
                        is_active=True
                    )
                               .order_by('last_used')  # 使用最少的优先
                               .first())

                    if not account:
                        # 其次选择限制已过期的账号
                        account = (TelethonAccount.objects
                                   .select_for_update()
                                   .filter(
                            status='limited',
                            limited_until__lte=now,
                            is_active=True
                        )
                                   .order_by('last_used')
                                   .first())

                    if account:
                        # 更新使用统计
                        account.last_used = now
                        account.request_count += 1
                        account.save()
                        logger.info(f"🔍 选中账号: {account.phone_number} (ID: {account.id})")

                    return account

            return await sync_to_async(_query_account_sync)()

        except Exception as e:
            logger.error(f"❌ 获取可用账号失败: {e}")
            return None

    @staticmethod
    async def update_account_status(account_id: int, status: str, error_message: str = '', limited_seconds: int = None):
        """
        异步更新账号的状态。
        使用事务和行级锁来确保操作的原子性。
        """
        try:
            await sync_to_async(_update_status_sync)(account_id, status, error_message, limited_seconds)
        except TelethonAccount.DoesNotExist:
            logger.error(f"❌ 无法更新状态，账号 ID {account_id} 不存在。")
        except Exception as e:
            logger.error(f"❌ 更新账号 ID {account_id} 状态时发生错误: {e}")

    @staticmethod
    async def login_account(account_id: int) -> bool:
        # ... (此方法逻辑正确，无需修改) ...
        try:
            account = await sync_to_async(TelethonAccount.objects.get)(pk=account_id)
        except TelethonAccount.DoesNotExist:
            logger.error(f"❌ 账号 ID {account_id} 不存在。")
            return False

        logger.info(f"🔄 开始为账号 {account.phone_number} (ID: {account.id}) 执行登录流程...")

        account.status = 'logging_in'
        account.error_message = ''
        await sync_to_async(account.save)()

        client = None
        try:
            client = await TelethonAccountManager._create_client(account)
            async with client:
                await client.start(
                    phone=lambda: input(f"\n请输入账号 {account.phone_number} 收到的验证码: ").strip(),
                    password=lambda: input("请输入两步验证密码（如未开启请直接回车）: ").strip() or None
                )

                session_string = client.session.save()

                account.status = 'authorized'
                account.session_string = session_string
                account.error_message = ''
                account.limited_until = None

                await sync_to_async(account.save)()

                logger.info(f"✅ 账号 {account.phone_number} 登录成功并已原子化保存 session 和状态。")
                return True

        except FloodWaitError as e:
            logger.warning(f"⏰ 账号 {account.phone_number} 因频繁操作被临时限制，需等待 {e.seconds} 秒。")
            account.status = 'limited'
            account.limited_until = datetime.now(timezone.utc) + timedelta(seconds=e.seconds)
            account.error_message = f"FloodWait: {e.seconds} seconds"
            await sync_to_async(account.save)()
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
            logger.error(f"❌ 账号 {account.phone_number} 登录失败：验证码无效或已过期。")
            account.status = 'error'
            account.error_message = str(e)
            await sync_to_async(account.save)()
        except SessionPasswordNeededError:
            logger.error(f"❌ 账号 {account.phone_number} 登录失败：需要两步验证密码，但用户未提供。")
            account.status = 'error'
            account.error_message = "SessionPasswordNeeded: Two-step verification required."
            await sync_to_async(account.save)()
        except Exception as e:
            logger.error(f"❌ 账号 {account.phone_number} 登录时发生未知错误: {e}", exc_info=True)
            account.status = 'error'
            account.error_message = f"Unexpected error: {str(e)}"
            await sync_to_async(account.save)()
        finally:
            if client and client.is_connected():
                await client.disconnect()
                logger.debug(f"📡 账号 {account.phone_number} 的客户端已断开连接。")

        return False

    @staticmethod
    def with_account_switching(max_retries: int = 3):
        """
        一个装饰器，用于包装需要 Telethon 客户端的异步任务函数。
        它会自动处理账号选择、切换和重试逻辑。
        """

        def decorator(task_func):
            @wraps(task_func)
            async def wrapper(*args, **kwargs):
                retries = 0

                while retries < max_retries:
                    # 1. 每次重试都重新从数据库获取一个可用账号
                    account = await TelethonAccountManager.get_available_account()
                    if not account:
                        logger.warning(f"⚠️  重试 {retries + 1}/{max_retries}：当前没有可用账号。等待 5 秒后重试...")
                        retries += 1
                        await asyncio.sleep(5)
                        continue

                    client = None
                    try:
                        # 2. 创建并启动客户端
                        client = await TelethonAccountManager._create_client(account)
                        async with client:
                            # 3. 将客户端和账号信息作为参数传递给被装饰的任务函数
                            kwargs['client'] = client
                            kwargs['account'] = account

                            # 4. 执行核心任务
                            logger.info(f"🚀 使用账号 {account.phone_number} 执行任务...")
                            result = await task_func(*args, **kwargs)

                        # 5. 任务成功执行，返回结果
                        logger.info(f"✅ 账号 {account.phone_number} 任务执行成功。")
                        return result

                    except FloodWaitError as e:
                        # 6. 处理账号限流错误 - 必须切换账号
                        retries += 1
                        logger.warning(
                            f"⏰ 账号 {account.phone_number} (ID: {account.id}) 被临时限制 {e.seconds} 秒。"
                            f"将其标记为受限，并切换账号重试 (重试 {retries}/{max_retries})..."
                        )
                        # 异步更新账号状态为受限
                        await TelethonAccountManager.update_account_status(
                            account.id,
                            status='limited',
                            error_message=f"FloodWait: {e.seconds} seconds",
                            limited_seconds=e.seconds
                        )
                        # 无需长时间等待，立即尝试下一个账号
                        await asyncio.sleep(1)

                    except (UserBannedInChannelError, SessionRevokedError, AuthKeyError) as e:
                        # 7. 处理致命错误 - 账号永久/长期不可用
                        retries += 1
                        error_msg = str(e)
                        logger.error(
                            f"🔴 账号 {account.phone_number} (ID: {account.id}) 发生致命错误: {error_msg}。将其标记为不可用。"
                        )
                        status = 'banned' if isinstance(e, UserBannedInChannelError) else 'error'
                        await TelethonAccountManager.update_account_status(
                            account.id,
                            status=status,
                            error_message=error_msg
                        )
                        await asyncio.sleep(1)

                    except (PeerFloodError, ChannelPrivateError) as e:
                        # 8. 处理临时性或非账号本身的错误 - 不标记账号为error
                        retries += 1
                        error_msg = str(e)
                        await TelethonAccountManager.update_account_status(
                            account.id,
                            status=status,
                            error_message=error_msg
                        )
                        logger.warning(
                            f"⚠️  账号 {account.phone_number} (ID: {account.id}) 执行任务失败: {error_msg}。这可能是一个临时问题，将直接切换账号重试 (重试 {retries}/{max_retries})..."
                        )
                        # 不更新账号状态为 'error'，仅日志记录
                        await asyncio.sleep(1)

                    except Exception as e:
                        # 9. 处理其他未知错误 - 保守处理
                        retries += 1
                        logger.error(
                            f"❓ 账号 {account.phone_number} (ID: {account.id}) 执行任务时发生未知错误: {e}",
                            exc_info=True
                        )
                        # 未知错误，为安全起见，暂时将账号标记为 error，以便人工检查
                        await TelethonAccountManager.update_account_status(
                            account.id,
                            status='error',
                            error_message=f"Unexpected error: {str(e)}"
                        )
                        await asyncio.sleep(2)

                    finally:
                        # 确保客户端被正确断开
                        if client and client.is_connected():
                            try:
                                await client.disconnect()
                                logger.debug(f"📡 账号 {account.phone_number} 的客户端已断开连接。")
                            except Exception as e:
                                logger.warning(f"⚠️  断开账号 {account.phone_number} 客户端连接时发生错误: {e}")

                # 10. 所有重试都失败
                logger.error(f"❌ 所有 {max_retries} 次尝试均失败，任务最终失败。")
                return None

            return wrapper

        return decorator


def _update_status_sync(account_id: int, status: str, error_message: str = '', limited_seconds: int = None):
    """
    同步函数，用于在事务中更新账号状态。
    这是一个内部辅助函数，不应被外部直接调用。
    """
    with transaction.atomic():
        account = TelethonAccount.objects.select_for_update().get(pk=account_id)

        account.status = status
        account.error_message = error_message

        if limited_seconds and status == 'limited':
            account.limited_until = datetime.now(timezone.utc) + timedelta(seconds=limited_seconds)
        elif status == 'authorized':
            account.limited_until = None  # 重置限制时间

        account.save()
        logger.info(f"📊 账号 {account.phone_number} (ID: {account.id}) 状态已更新为: {status}")


# 为了方便，创建一个默认的管理器实例
default_manager = TelethonAccountManager()
