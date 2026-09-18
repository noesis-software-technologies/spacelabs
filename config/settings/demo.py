"""Démo : identique à dev mais sans debug-toolbar (captures/vidéo propres)."""
from .dev import *  # noqa: F401,F403

INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

CSRF_TRUSTED_ORIGINS = ["https://*.trycloudflare.com"]
