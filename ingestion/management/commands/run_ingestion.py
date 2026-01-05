from django.core.management.base import BaseCommand
import asyncio
from ingestion.pipelines import run_ingestion_pipeline

class Command(BaseCommand):
    help = "Run ingestion pipeline"

    def handle(self, *args, **kwargs):
        asyncio.run(run_ingestion_pipeline())
        self.stdout.write(self.style.SUCCESS("Ingestion pipeline completed"))
