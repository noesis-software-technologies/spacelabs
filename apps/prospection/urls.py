from django.urls import path

from . import views

app_name = "prospection"

urlpatterns = [
    path("", views.cockpit, name="cockpit"),
    path("board/", views.board, name="board"),
    path("export.csv", views.export_csv, name="export_csv"),
    path("modeles/", views.modeles, name="modeles"),
    path("<int:pk>/", views.opportunity_detail, name="detail"),
    path("<int:pk>/stage/", views.set_stage, name="set_stage"),
    path("<int:pk>/field/", views.update_field, name="update_field"),
    path("<int:pk>/note/", views.save_note, name="save_note"),
    path("<int:pk>/step/add/", views.add_step, name="add_step"),
    path("<int:pk>/step/generate/", views.generate_steps, name="generate_steps"),
    path("<int:pk>/ai/offer/", views.ai_offer, name="ai_offer"),
    path("<int:pk>/ai/relance/", views.ai_relance, name="ai_relance"),
    path("<int:pk>/ai/next/", views.ai_next, name="ai_next"),
    path("step/<int:pk>/toggle/", views.toggle_step, name="toggle_step"),
]
