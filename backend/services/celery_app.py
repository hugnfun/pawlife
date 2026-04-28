"""
Celery 应用配置。

使用 Redis 作为 broker 和 result backend。
"""

from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery_app = Celery(
    "pawlife",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["services.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

# 任务路由
celery_app.conf.task_routes = {
    "services.tasks.generate_daily_report": {"queue": "default"},
    "services.tasks.generate_morning_reports": {"queue": "default"},
    "services.tasks.send_reminder": {"queue": "default"},
    "services.tasks.check_and_send_reminders": {"queue": "default"},
    "services.tasks.process_nutrition": {"queue": "default"},
}

# Beat 定时任务调度
celery_app.conf.beat_schedule = {
    # 每分钟检查待发送提醒
    "check-reminders-every-minute": {
        "task": "services.tasks.check_and_send_reminders",
        "schedule": 60.0,
    },
    # 每天早上 7:00 生成每日晨报
    "morning-reports-daily": {
        "task": "services.tasks.generate_morning_reports",
        "schedule": crontab(hour=7, minute=0),
    },
}
