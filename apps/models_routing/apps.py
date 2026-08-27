from django.apps import AppConfig


class ModelsRoutingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.models_routing"
    label = "models_routing"
    verbose_name = "Routage de modèles (ADR-5)"
