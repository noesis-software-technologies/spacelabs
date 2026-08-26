from django.urls import path

from . import views

app_name = "observer"

urlpatterns = [
    path("", views.observer_page, name="page"),
    path("grille/", views.observer_grid, name="grid"),
    path("stream/", views.observer_stream, name="stream"),
    path("regie/", views.regie, name="regie"),
    path("regie/regles/nouvelle/", views.rule_create, name="rule_create"),
    path("regie/regles/<int:rule_id>/supprimer/", views.rule_delete, name="rule_delete"),
]
