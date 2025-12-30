# telethon_account/management/commands/login_telethon_account.py

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from telethon_account.models import TelethonAccount
from telethon_account.telethon_manager import TelethonAccountManager
import asyncio # <--- 新增导入
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '列出所有未登录的 Telethon 账号，选择后执行登录并保存 session。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            help='指定要登录的手机号 (例如: +8613800138000)，跳过列表选择'
        )
        parser.add_argument(
            '--id',
            type=int,
            help='指定要登录的账号 ID，跳过列表选择'
        )

    def _list_unlogged_accounts(self) -> list[TelethonAccount]:
        """列出所有未登录的账号（idle/error 状态，无有效 session）"""
        unlogged_accounts = TelethonAccount.objects.filter(
            Q(status__in=['idle', 'error']) &
            (Q(session_string__exact='') | Q(session_string__isnull=True))
        ).order_by('id')

        if not unlogged_accounts.exists():
            self.stdout.write(self.style.WARNING('⚠️  没有找到未登录的 Telethon 账号。'))
            return []

        self.stdout.write(self.style.SUCCESS('\n📋 未登录的账号列表：'))
        for idx, account in enumerate(unlogged_accounts, 1):
            self.stdout.write(
                f'[{idx}] ID: {account.id} | 手机号: {account.phone_number} | 状态: {account.get_status_display()}'
            )
        self.stdout.write('')  # 空行分隔
        return list(unlogged_accounts)

    def _select_account(self, accounts: list[TelethonAccount]) -> TelethonAccount:
        """让用户从列表中选择一个账号"""
        while True:
            user_input = input('请输入要登录的账号序号（直接回车退出）：').strip()
            if not user_input:
                raise CommandError('🚫 用户取消操作。')

            try:
                selected_idx = int(user_input) - 1
                if 0 <= selected_idx < len(accounts):
                    return accounts[selected_idx]
                else:
                    self.stdout.write(self.style.ERROR(f'❌ 无效序号！请输入 1-{len(accounts)} 之间的数字。'))
            except ValueError:
                self.stdout.write(self.style.ERROR('❌ 输入无效！请输入数字序号。'))

    def handle(self, *args, **options):
        """命令入口点：优先指定账号，否则列出选择"""
        phone = options.get('phone')
        account_id = options.get('id')
        account = None

        # 1. 优先处理指定账号的情况
        if account_id:
            try:
                account = TelethonAccount.objects.get(pk=account_id)
            except TelethonAccount.DoesNotExist:
                raise CommandError(f'❌ 账号 ID {account_id} 不存在。')
        elif phone:
            try:
                account = TelethonAccount.objects.get(phone_number=phone)
            except TelethonAccount.DoesNotExist:
                raise CommandError(f'❌ 手机号 {phone} 未在系统中注册。')

        # 2. 未指定账号：列出所有未登录账号让用户选择
        if not account:
            unlogged_accounts = self._list_unlogged_accounts()
            if not unlogged_accounts:
                return
            account = self._select_account(unlogged_accounts)

        # 3. 确认登录
        self.stdout.write('-' * 50)
        self.stdout.write(self.style.SUCCESS(f'📌 已选择账号：{account.phone_number}'))
        self.stdout.write('-' * 50)

        confirm = input('是否确认登录该账号？(y/n，默认 y)：').strip().lower()
        if confirm not in ('', 'y', 'yes'):
            raise CommandError('🚫 用户取消登录。')

        # 4. 执行登录
        # 4. 执行登录
        self.stdout.write(self.style.NOTICE(f'\n🔄 正在执行登录流程...（请按照提示输入验证码/两步验证密码）'))

        # 调用异步的 login_account 方法
        success = asyncio.run(TelethonAccountManager.login_account(account.id))

        # 5. 登录结果反馈
        if success:
            self.stdout.write(self.style.SUCCESS(f'\n✅ 账号 {account.phone_number} 登录成功！'))
            self.stdout.write(f'📝 已保存 session 到数据库，状态已更新为 "已授权"。')
        else:
            self.stdout.write(self.style.ERROR(f'\n❌ 账号 {account.phone_number} 登录失败，请查看日志了解详情。'))