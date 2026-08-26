from django.urls import path

from . import views

app_name = "ops"

urlpatterns = [
    path("jauges/", views.gauges, name="gauges"),
    path("mcp/<int:alert_id>/resoudre/", views.resolve_mcp, name="resolve_mcp"),
]
