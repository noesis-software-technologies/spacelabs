"""Vues d'exploitation : jauges de la sidebar et gestion des alertes MCP.

Les jauges sont calculées EN DIRECT depuis la DB à chaque requête (précis,
cross-process), le dernier UsageSnapshot ne servant qu'à dater/tendre.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.ops.models import MCPAlert, UsageSnapshot
from apps.ops.services import usage_for_owner


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
