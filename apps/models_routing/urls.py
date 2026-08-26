from django.urls import path

from . import views

app_name = "models_routing"

urlpatterns = [
    path("statusbar/<slug:slug>/", views.statusbar_fragment, name="statusbar"),
    path("runs/", views.runs_panel, name="runs"),
]
