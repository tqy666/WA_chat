import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

broker_url = os.getenv("CELERY_BROKER_URL", "redis://openwa-redis:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://openwa-redis:6379/0")

app = Celery(
    "whatsapp_tasks",
    broker=broker_url,
    backend=result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # 关键：防止任务堆积
)

