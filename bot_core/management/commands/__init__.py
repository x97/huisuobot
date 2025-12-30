from django.core.management.base import BaseCommand
from django.conf import settings
import logging

from bot_core.bot import create_bot


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start Telegram Bot"

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        if not token:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in settings"))
            return

        self.stdout.write(self.style.SUCCESS("Starting Telegram Bot..."))

        try:
            updater = create_bot(token)
            updater.start_polling()
            self.stdout.write(self.style.SUCCESS("Bot is now running"))
            updater.idle()

        except Exception as e:
            logger.exception("Bot crashed with exception")
            self.stderr.write(self.style.ERROR(f"Bot crashed: {e}"))
