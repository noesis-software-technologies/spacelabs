from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import TemplateView

from apps.vitrine.views import landing
from config.dashboard_view import (
    spacelabs_dashboard,
    spacelabs_usage,
    spacelabs_workspaces,
)


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", landing, name="landing"),
    path("privacy/", TemplateView.as_view(template_name="legal/privacy.html"), name="privacy"),
    path("data-deletion/", TemplateView.as_view(template_name="legal/data_deletion.html"), name="data_deletion"),
    path("v2/", TemplateView.as_view(template_name="landing_v2.html"), name="landing_v2"),
    path("v3/", TemplateView.as_view(template_name="landing_v3.html"), name="landing_v3"),
    path("v4/", TemplateView.as_view(template_name="landing_v4.html"), name="landing_v4"),
    path("v5/", TemplateView.as_view(template_name="landing_v5.html"), name="landing_v5"),
    path("v6/", TemplateView.as_view(template_name="landing_v6.html"), name="landing_v6"),
    path("auth/", include("apps.comptes.urls")),
    path("cockpit/", include("apps.workspaces.urls")),
    path("observer/", include("apps.observer.urls")),
    path("ops/", include("apps.ops.urls")),
    path("missions/", include("apps.tasker.urls")),
    path("skills/", include("apps.skills.urls")),
    path("voice/", include("apps.voice.urls")),
    path("routage/", include("apps.models_routing.urls")),
    path("vitrine/", include("apps.vitrine.urls")),
    path("veille/", include("apps.veille.urls")),
    path("comms/", include("apps.comms.urls")),
    path("dashboard/", spacelabs_dashboard, name="dashboard"),
    path("dashboard/workspaces/", spacelabs_workspaces, name="dashboard_workspaces"),
    path("dashboard/usage/", spacelabs_usage, name="dashboard_usage"),
    path("django-admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
]

# La toolbar n'est montée que si l'APP est activée (settings dev), pas
# simplement si le paquet est importable — sinon `check --deploy` en prod
# charge des modèles hors INSTALLED_APPS et explose.
if "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns = [path("__debug__/", include("debug_toolbar.urls"))] + urlpatterns

# Sert les médias téléchargés en local pendant le dev (images des communiqués).
if settings.DEBUG:
    from django.conf.urls.static import static as _static
    urlpatterns += _static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
