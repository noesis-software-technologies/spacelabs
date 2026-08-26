"""Settings communs SpaceLabs — tout secret/spécifique vient de l'environnement."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    REDIS_URL=(str, "redis://127.0.0.1:6379/0"),
    COCKPIT_MAX_PANES=(int, 16),
    COCKPIT_OWNER_MAX_PANES=(int, 0),  # 0 = retombe sur COCKPIT_MAX_PANES
    COCKPIT_BUFFER_BYTES=(int, 200_000),
    COCKPIT_DEFAULT_CMD=(str, "claude"),
    COCKPIT_ALLOWED_CMDS=(list, ["claude", "bash", "sh"]),
    COCKPIT_HEARTBEAT_STALE_SECONDS=(int, 90),
    COCKPIT_EVENTLOG_RETENTION_DAYS=(int, 30),
    COCKPIT_EVENTLOG_ARCHIVE_DIR=(str, ""),
    COCKPIT_MCP_AUTH_PATTERNS=(list, ["needs authentication", "requires authentication", "run /mcp", "authenticate with"]),
    COCKPIT_USAGE_CMD=(list, []),
    COCKPIT_SNAPSHOT_EVERY_SECONDS=(int, 60),
    COCKPIT_REAP_EVERY_SECONDS=(int, 120),
    COCKPIT_TASKER_TICK_SECONDS=(int, 5),
    COCKPIT_TASKER_TASK_TIMEOUT_SECONDS=(int, 900),
    COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS=(int, 120),
    COCKPIT_LAN_TOKEN=(str, ""),
    COCKPIT_STT_BACKEND=(str, "webspeech"),
    COCKPIT_STT_MODEL=(str, "nyralabs/faster_CrisperWhisper"),
    COCKPIT_STT_DEVICE=(str, "auto"),
    COCKPIT_STT_COMPUTE_TYPE=(str, "int8"),
    COCKPIT_STT_LANGUAGE=(str, "fr"),
    COCKPIT_STT_FAKE_TRANSCRIPT=(str, "ceci est une transcription de test"),
    TIME_ZONE=(str, "Europe/Paris"),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",  # runserver ASGI en dev — avant staticfiles
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # tiers
    "channels",
    "django_htmx",
    # métier
    "apps.common",
    "apps.comptes",
    "apps.runtime",
    "apps.workspaces",
    "apps.observer",
    "apps.chat",
    "apps.ops",
    "apps.tasker",
    "apps.skills",
    "apps.voice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.common.middleware.LanTokenMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.common.context_processors.cockpit_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db_url("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_USER_MODEL = "comptes.User"
LOGIN_URL = "comptes:login"
LOGIN_REDIRECT_URL = "workspaces:home"
LOGOUT_REDIRECT_URL = "comptes:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Celery (broker = Redis ; les tâches arrivent au Sprint 5, la plomberie est J0) ──
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = env("REDIS_URL")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TIMEZONE = TIME_ZONE

# ── Cockpit (runtime des panes) ──
COCKPIT_MAX_PANES = env("COCKPIT_MAX_PANES")
# Plafond par compte, tous workspaces confondus (0 = même valeur que ci-dessus).
COCKPIT_OWNER_MAX_PANES = env("COCKPIT_OWNER_MAX_PANES")
COCKPIT_BUFFER_BYTES = env("COCKPIT_BUFFER_BYTES")
COCKPIT_DEFAULT_CMD = env("COCKPIT_DEFAULT_CMD")
# Liste blanche des exécutables spawnables — garde-fou : le WS ne lance jamais
# une commande arbitraire, seulement un binaire approuvé ici.
COCKPIT_ALLOWED_CMDS = env("COCKPIT_ALLOWED_CMDS")
# Presets d'agents du sélecteur « Nouvel agent ». Vide = liste intégrée par défaut.
# Fournir une liste (JSON d'environnement, ou surcharge Python en settings) la REMPLACE.
# Format : [{"key": "claude", "label": "Claude Code", "kind": "pty",
#            "cmd": "claude", "color": "var(--claude)", "icon": "terminal",
#            "description": "…"}]  (kind ∈ {pty, headless} ; cmd requis si pty)
COCKPIT_AGENT_PRESETS = env.json("COCKPIT_AGENT_PRESETS", default=[])


# ── Logging structuré : console en dev, fichier/JSON possible en prod via env ──
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "console"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "spacelabs": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

# ── Chat headless (Sprint 4) ──
# Binaire Claude Code + arguments fixes construits côté serveur (jamais saisis
# par l'utilisateur). En prod : "claude". En test : le faux binaire stream-json.
COCKPIT_CLAUDE_BIN = env("COCKPIT_CLAUDE_BIN", default="claude")
# Args de base du mode chat. --dangerously-skip-permissions est nécessaire pour
# que les agents exécutent des outils sans invite interactive : à activer en
# connaissance de cause (voir README, section Sécurité).
COCKPIT_CLAUDE_HEADLESS_ARGS = env(
    "COCKPIT_CLAUDE_HEADLESS_ARGS",
    default=["-p", "--output-format", "stream-json", "--input-format", "stream-json", "--verbose"],
)
# Boutons d'amorce du composer (label → prompt de départ, éditable).
# ── Exploitation (Sprint 5) ──
COCKPIT_HEARTBEAT_STALE_SECONDS = env("COCKPIT_HEARTBEAT_STALE_SECONDS")
COCKPIT_EVENTLOG_RETENTION_DAYS = env("COCKPIT_EVENTLOG_RETENTION_DAYS")
COCKPIT_EVENTLOG_ARCHIVE_DIR = env("COCKPIT_EVENTLOG_ARCHIVE_DIR")
COCKPIT_MCP_AUTH_PATTERNS = env("COCKPIT_MCP_AUTH_PATTERNS")
COCKPIT_USAGE_CMD = env("COCKPIT_USAGE_CMD")
# Réconciliation au boot : marque morts les panes 'running' d'une génération
# Daphne antérieure. La reprise auto (respawn claude --continue) reste
# désactivée par défaut — l'attache/le respawn à la demande couvrent ce besoin.
COCKPIT_RESUME_ON_BOOT = env.bool("COCKPIT_RESUME_ON_BOOT", default=False)
# Jeton partagé pour protéger l'accès LAN (vide = désactivé, dev localhost).
COCKPIT_LAN_TOKEN = env("COCKPIT_LAN_TOKEN")
COCKPIT_TASKER_TASK_TIMEOUT_SECONDS = env("COCKPIT_TASKER_TASK_TIMEOUT_SECONDS")
COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS = env("COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS")
# Boucle d'orchestration dans le processus ASGI (désactivable en test/CI).
COCKPIT_TASKER_AUTORUN = env.bool("COCKPIT_TASKER_AUTORUN", default=True)

# ── Reconnaissance vocale (Sprint 7) ──
# "webspeech" : reconnaissance navigateur (défaut). "crisperwhisper" : serveur
# (faster-whisper + CrisperWhisper, verbatim). "fake" : transcripteur de test.
COCKPIT_STT_BACKEND = env("COCKPIT_STT_BACKEND")
COCKPIT_STT_MODEL = env("COCKPIT_STT_MODEL")
COCKPIT_STT_DEVICE = env("COCKPIT_STT_DEVICE")
COCKPIT_STT_COMPUTE_TYPE = env("COCKPIT_STT_COMPUTE_TYPE")
COCKPIT_STT_LANGUAGE = env("COCKPIT_STT_LANGUAGE")
COCKPIT_STT_FAKE_TRANSCRIPT = env("COCKPIT_STT_FAKE_TRANSCRIPT")

# Planification Celery beat (statique — pas de scheduler DB à administrer).
CELERY_BEAT_SCHEDULE = {
    "tasker-tick": {
        "task": "tasker.tick_all",
        # Battement d'orchestration : décision pure DB, donc bon marché.
        "schedule": float(env("COCKPIT_TASKER_TICK_SECONDS")),
    },
    "snapshot-usage": {
        "task": "ops.snapshot_usage",
        "schedule": float(env("COCKPIT_SNAPSHOT_EVERY_SECONDS")),
    },
    "reap-zombies": {
        "task": "ops.reap_zombies",
        "schedule": float(env("COCKPIT_REAP_EVERY_SECONDS")),
    },
    "scan-mcp-auth": {
        "task": "ops.scan_mcp_auth",
        "schedule": 120.0,
    },
    "archive-eventlog": {
        "task": "ops.archive_eventlog",
        "schedule": 3600.0,  # horaire
    },
}

COCKPIT_PRIMING_PROMPTS = env.json(
    "COCKPIT_PRIMING_PROMPTS",
    default=[
        {"label": "Build", "prompt": "Implémente la prochaine étape la plus utile, puis lance les tests."},
        {"label": "Plan", "prompt": "Analyse le code et propose un plan détaillé avant de coder."},
        {"label": "Fix", "prompt": "Trouve et corrige le bug le plus probable, cause racine, avec un test."},
    ],
)
