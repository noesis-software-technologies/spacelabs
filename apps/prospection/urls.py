from django.urls import path

from . import views

app_name = "prospection"

urlpatterns = [
    path("", views.board, name="board"),
    path("modeles/", views.modeles, name="modeles"),
    path("<int:pk>/", views.opportunity_detail, name="detail"),
    path("<int:pk>/stage/", views.set_stage, name="set_stage"),
    path("<int:pk>/field/", views.update_field, name="update_field"),
    path("<int:pk>/note/", views.save_note, name="save_note"),
]
