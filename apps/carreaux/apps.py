from django.apps import AppConfig


class CarreauxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.carreaux"
    verbose_name = "Boutique carreaux"

    def ready(self):
        import apps.carreaux.signals  # noqa: F401
