from django.urls import path

from . import views

app_name = "prospection"

urlpatterns = [
    path("", views.board, name="board"),
    path("<int:pk>/", views.opportunity_detail, name="detail"),
    path("<int:pk>/stage/", views.set_stage, name="set_stage"),
    path("<int:pk>/note/", views.save_note, name="save_note"),
]
