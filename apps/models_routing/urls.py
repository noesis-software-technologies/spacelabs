from django.urls import path

from . import views

app_name = "models_routing"

urlpatterns = [
    path("statusbar/<slug:slug>/", views.statusbar_fragment, name="statusbar"),
    path("runs/", views.runs_panel, name="runs"),
    path("openclaw-stats/", views.openclaw_stats, name="openclaw_stats"),
    path("openclaw-stats/log/", views.openclaw_log_exchange, name="openclaw_log"),
]
