"""Dashboard central SpaceLabs (hub) — KPIs live + accès modules."""
from django.shortcuts import render


def spacelabs_dashboard(request):
    ctx = {"kpi": {}, "modules": []}
    # Vitrine
    try:
        from apps.vitrine.catalogue import PRODUITS
        ctx["kpi"]["produits"] = len(PRODUITS)
    except Exception:
        ctx["kpi"]["produits"] = "—"
    # Veille (constellation 13 Atmosphère)
    try:
        from apps.veille.models import Blog, PressItem
        ctx["kpi"]["rp_total"] = PressItem.objects.count()
        ctx["kpi"]["rp_atrier"] = PressItem.objects.filter(categorie="autre").count()
        ctx["kpi"]["blogs"] = Blog.objects.count()
    except Exception:
        ctx["kpi"].update(rp_total="—", rp_atrier="—", blogs="—")
    # Comms (inbox unifié)
    try:
        from apps.comms.models import Message
        base = Message.objects.exclude(statut="archive")
        ctx["kpi"]["msg_total"] = Message.objects.count()
        ctx["kpi"]["msg_reply"] = base.filter(needs_reply=True).count()
        ctx["kpi"]["msg_haute"] = base.filter(priorite="haute").count()
    except Exception:
        ctx["kpi"].update(msg_total="—", msg_reply="—", msg_haute="—")
    # Workspaces / agents
    try:
        from apps.workspaces.models import Workspace
        ctx["kpi"]["workspaces"] = Workspace.objects.count()
    except Exception:
        ctx["kpi"]["workspaces"] = "—"
    return render(request, "dashboard/index.html", ctx)
