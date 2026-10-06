from celery import Celery
from clip_shared.config import get_settings

settings = get_settings()

celery_app = Celery(
    "clip_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["worker.tasks.pipeline"],
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
    task_default_queue="cpu",
    task_queues={
        "cpu": {},
        "gpu": {},
    },
    task_routes={
        "worker.tasks.pipeline.run_stage": lambda name, args, kwargs, options, task=None: {
            "queue": "gpu" if (args and len(args) > 1 and args[1] == "transcribe") else "cpu"
        },
    },
)
