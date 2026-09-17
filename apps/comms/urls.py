from django.urls import path

from . import views

app_name = "comms"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),
]
