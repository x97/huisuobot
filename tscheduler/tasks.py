from ingestion.pipelines import run_ingestion_pipeline

from celery import shared_task
import asyncio


# Celery 任务包装器（同步调用异步函数）
@shared_task
def celery_run_ingestion_pipeline():
    """
    每20分钟执行的 Celery 任务
    包装并运行你的 async 函数
    """
    # 运行 async 函数（Celery 是同步框架，必须这样调用）
    asyncio.run(run_ingestion_pipeline())
    return "✅ Ingestion pipeline 执行完成"
