"""Plomberie Celery (J0). Les tâches métier arrivent au Sprint 5."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("spacelabs")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
