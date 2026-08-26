from django.urls import path

from . import views

app_name = "voice"

urlpatterns = [
    path("transcribe/", views.transcribe, name="transcribe"),
    path("commande/", views.command, name="command"),
]
