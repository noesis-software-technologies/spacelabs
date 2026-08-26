"""ASGI natif dès J0 ([REALTIME]=oui) — HTTP + WebSocket."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.runtime import routing  # noqa: E402
from apps.runtime.lifespan import LifespanApp  # noqa: E402
from apps.runtime.startup import on_server_boot  # noqa: E402

# Réconciliation + démarrage du battement, dès l'import de ce module dans le
# processus serveur (robuste, indépendant du support 'lifespan' du serveur).
on_server_boot()

application = ProtocolTypeRouter(
    {
        # Réconciliation + battement de cœur au (dé)marrage de Daphne (S5).
        "lifespan": LifespanApp(),
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns))
        ),
    }
)
