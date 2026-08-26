from django.apps import AppConfig


class RuntimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.runtime"
    label = "runtime"

    def ready(self):
        from . import checks  # noqa: F401 — contrôles de configuration
