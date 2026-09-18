"""Vues d'exploitation : jauges de la sidebar et gestion des alertes MCP.

Les jauges sont calculées EN DIRECT depuis la DB à chaque requête (précis,
cross-process), le dernier UsageSnapshot ne servant qu'à dater/tendre.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.ops.models import MCPAlert, UsageSnapshot
from apps.ops.services import usage_for_owner


def health(request):
    """Supervision de la stack — JSON agrégé, sans secret.

    Composants : base de données, modèle local (llama.cpp :8081), configuration
    Meta (booléens présents/absents — jamais les valeurs), volumétrie métier.
    Renvoie 200 si tout est « ok », 503 si un composant critique est « down ».
    Public volontairement (probe monitoring), mais n'expose aucune donnée
    sensible : uniquement des états et des compteurs.
    """
    import time
    import urllib.request

    from django.conf import settings
    from django.db import connection

    comps = {}

    # --- Base de données (critique) ---
    t0 = time.perf_counter()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        comps["db"] = {"status": "ok", "ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:  # noqa: BLE001
        comps["db"] = {"status": "down", "error": type(e).__name__}

    # --- Modèle local (non critique : dégradé si absent) ---
    base = (getattr(settings, "LOCAL_LLM_BASE", "") or "http://127.0.0.1:8081").rstrip("/")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=1.5) as r:
            comps["local_llm"] = {
                "status": "ok" if r.status == 200 else "degraded",
                "ms": round((time.perf_counter() - t0) * 1000, 1),
            }
    except Exception:  # noqa: BLE001
        comps["local_llm"] = {"status": "down"}

    # --- Configuration Meta (présence des jetons, jamais les valeurs) ---
    comps["meta_config"] = {
        "verify_token": bool(getattr(settings, "META_VERIFY_TOKEN", "")),
        "app_secret": bool(getattr(settings, "META_APP_SECRET", "")),
        "whatsapp_token": bool(getattr(settings, "WHATSAPP_TOKEN", "")),
        "page_token": bool(getattr(settings, "META_PAGE_TOKEN", "")),
        "ig_token": bool(getattr(settings, "META_IG_TOKEN", "")),
    }

    # --- Volumétrie métier (compteurs) ---
    try:
        from apps.comms.models import Message
        comps["comms"] = {
            "status": "ok",
            "messages": Message.objects.count(),
            "a_repondre": Message.objects.filter(needs_reply=True).exclude(statut="archive").count(),
        }
    except Exception as e:  # noqa: BLE001
        comps["comms"] = {"status": "down", "error": type(e).__name__}

    try:
        from apps.veille.models import PressItem
        total = PressItem.objects.count()
        drafted = PressItem.objects.exclude(draft_statut="vide").count()
        comps["veille"] = {"status": "ok", "items": total, "drafts": drafted}
    except Exception:  # noqa: BLE001
        comps["veille"] = {"status": "n/a"}

    # Santé globale : « down » seulement si un composant critique tombe.
    critical_ok = comps["db"]["status"] == "ok"
    overall = "ok" if critical_ok else "down"
    payload = {"status": overall, "components": comps}
    return JsonResponse(payload, status=200 if critical_ok else 503)


@login_required
def gauges(request):
    data = usage_for_owner(request.user)
    last = UsageSnapshot.objects.filter(owner=request.user).first()
    pct = 0
    if data["max_panes"]:
        pct = min(100, round(100 * data["active_panes"] / data["max_panes"]))
    alerts = MCPAlert.objects.filter(
        pane__workspace__owner=request.user, resolved=False
    ).count()
    # Niveau visuel de la jauge (.ds-gauge-fill[data-level]) : vert tant qu'il
    # reste de la place, orange à l'approche du plafond, rouge au plafond.
    level = "full" if pct >= 100 else ("warn" if pct >= 75 else "ok")
    context = {
        "usage": data,
        "panes_pct": pct,
        "panes_level": level,
        "last_snapshot": last,
        "external": last.external if last else None,
        "mcp_alerts": alerts,
    }
    return render(request, "ops/partials/_gauges.html", context)


@login_required
@require_POST
def resolve_mcp(request, alert_id):
    updated = MCPAlert.objects.filter(
        pk=alert_id, pane__workspace__owner=request.user
    ).update(resolved=True)
    if not updated:
        return HttpResponse(status=404)
    return HttpResponse("")
