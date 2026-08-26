from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("auth/", include("apps.comptes.urls")),
    path("cockpit/", include("apps.workspaces.urls")),
    path("observer/", include("apps.observer.urls")),
    path("ops/", include("apps.ops.urls")),
    path("missions/", include("apps.tasker.urls")),
    path("skills/", include("apps.skills.urls")),
    path("voice/", include("apps.voice.urls")),
    path("django-admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
]

# La toolbar n'est montée que si l'APP est activée (settings dev), pas
# simplement si le paquet est importable — sinon `check --deploy` en prod
# charge des modèles hors INSTALLED_APPS et explose.
if "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns = [path("__debug__/", include("debug_toolbar.urls"))] + urlpatterns
