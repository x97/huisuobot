from django.core.management.base import BaseCommand
from bot_core.bot import leave_unallowed_groups_on_startup


class Command(BaseCommand):
    help = "Force the bot to leave all unallowed groups/channels immediately."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Running leave_unallowed_groups_on_startup..."))

        try:
            leave_unallowed_groups_on_startup()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
