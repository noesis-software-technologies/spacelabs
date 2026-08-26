from django.apps import AppConfig


class TaskerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasker"
    label = "tasker"
    verbose_name = "Master Tasker"

    def ready(self):
        from . import signals  # noqa: F401  — branche la détection de fin
