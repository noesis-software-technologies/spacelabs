"""Prod locale durcie — `manage.py check --deploy` doit être vert avec ce module.

« Prod » = l'instance qui tourne pendant les lives, exposée au LAN uniquement.
Le cockpit spawne des process avec les droits de l'utilisateur : ne JAMAIS
l'exposer sur Internet (voir README, section Sécurité).
"""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = env("SECRET_KEY")  # noqa: F405 — obligatoire, pas de défaut en prod

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL")]},  # noqa: F405
    },
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# HTTPS/HSTS : servi en LAN derrière un reverse proxy TLS local (ex. caddy).
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
