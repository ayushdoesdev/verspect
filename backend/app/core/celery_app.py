"""Celery application factory and beat schedule."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dependency_intelligence",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.services.tasks.scan_tasks",
        "app.services.tasks.analysis_tasks",
        "app.services.tasks.ai_advisor_tasks",
        "app.services.tasks.notification_tasks",
        "app.services.tasks.scheduled_tasks",
        "app.services.tasks.upgrade_simulation_tasks",
        "app.services.tasks.migration_engine_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    result_expires=86400,
    task_default_queue="default",
    task_routes={
        "app.services.tasks.scan_tasks.*": {"queue": "scans"},
        "app.services.tasks.analysis_tasks.*": {"queue": "analysis"},
        "app.services.tasks.ai_advisor_tasks.*": {"queue": "analysis"},
        "app.services.tasks.upgrade_simulation_tasks.*": {"queue": "analysis"},
        "app.services.tasks.migration_engine_tasks.*": {"queue": "analysis"},
        "app.services.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.services.tasks.scheduled_tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "daily-full-rescan": {
            "task": "app.services.tasks.scheduled_tasks.daily_rescan_all",
            "schedule": crontab(hour=3, minute=0),
        },
        "hourly-version-check": {
            "task": "app.services.tasks.scheduled_tasks.hourly_version_check",
            "schedule": crontab(minute=15),
        },
        "cleanup-stale-clones": {
            "task": "app.services.tasks.scheduled_tasks.cleanup_stale_clones",
            "schedule": crontab(hour=4, minute=30),
        },
        # Reaps jobs whose worker died or never picked them up. Runs frequently so
        # users see an actionable failure instead of an endless spinner.
        "reap-stale-jobs": {
            "task": "app.services.tasks.scheduled_tasks.cleanup_stale_scans",
            "schedule": 60.0,
        },
        "learn-migration-rules-new-releases": {
            "task": "app.services.tasks.migration_engine_tasks.learn_rules_for_new_releases",
            "schedule": crontab(minute=45),
        },
        # Apply scheduled downgrades / cancel→Evaluation at period end
        "apply-subscription-lifecycle": {
            "task": "app.services.tasks.scheduled_tasks.apply_subscription_lifecycle",
            "schedule": crontab(minute=5),
        },
    },
)


@celery_app.task(bind=True, name="app.core.celery_app.health_ping")
def health_ping(self) -> dict:
    return {"status": "ok", "task_id": self.request.id}
