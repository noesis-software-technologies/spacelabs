from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/cockpit/", consumers.CockpitConsumer.as_asgi()),
]
