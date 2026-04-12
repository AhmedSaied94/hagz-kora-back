import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("hagzkora")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "mark-completed-bookings-hourly": {
        "task": "apps.bookings.tasks.mark_completed_bookings",
        "schedule": crontab(minute=0),  # top of every hour
        "options": {"queue": "bookings"},
    },
}
