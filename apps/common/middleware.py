"""Middleware de garde par jeton LAN (Sprint 6).

Quand COCKPIT_LAN_TOKEN est défini, tout le serveur exige ce secret partagé —
pratique pour exposer le cockpit (et la vue télé) sur ton réseau local sans
l'ouvrir à n'importe qui. Le jeton se fournit une fois via ?token=… (posé en
cookie), ensuite le cookie suffit. Vide (défaut) ⇒ aucun effet (dev localhost).

Exemptions : la sonde /healthz et les fichiers statiques (sinon la page 403
elle-même serait cassée).
"""
from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

COOKIE = "cockpit_lan"


class LanTokenMiddleware(MiddlewareMixin):
    def process_request(self, request):
        token = settings.COCKPIT_LAN_TOKEN
        if not token:
            return None
        path = request.path
        if path == "/healthz" or path.startswith(settings.STATIC_URL):
            return None
        # Fourni dans l'URL ⇒ on pose le cookie et on laisse passer.
        provided = request.GET.get("token")
        if provided and provided == token:
            request._lan_set_cookie = True
            return None
        if request.COOKIES.get(COOKIE) == token:
            return None
        return HttpResponse(
            "Accès protégé. Ajoute ?token=… à l'URL pour accéder à ce cockpit.",
            status=403, content_type="text/plain; charset=utf-8",
        )

    def process_response(self, request, response):
        if getattr(request, "_lan_set_cookie", False):
            # Cookie de session (durée de vie du navigateur), SameSite Lax.
            response.set_cookie(
                COOKIE, settings.COCKPIT_LAN_TOKEN, httponly=True, samesite="Lax"
            )
        return response
