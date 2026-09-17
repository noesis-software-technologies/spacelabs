from django.urls import path

from . import views

app_name = "comms"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("message/<int:pk>/reply/", views.message_reply, name="message_reply"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),
    path("meta/webhook/", views.meta_webhook, name="meta_webhook"),
]
