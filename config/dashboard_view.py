"""Dashboard central SpaceLabs (hub) — KPIs live + accès modules."""
from django.shortcuts import render


def spacelabs_dashboard(request):
    ctx = {"kpi": {}, "modules": [], "active_nav": "dashboard"}
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
        # aperçu embarqué : prioritaires puis à répondre
        ctx["inbox_preview"] = list(
            base.filter(priorite="haute")[:6]
        ) or list(base.filter(needs_reply=True)[:6])
    except Exception:
        ctx["kpi"].update(msg_total="—", msg_reply="—", msg_haute="—")
        ctx["inbox_preview"] = []
    # Veille : derniers communiqués
    try:
        from apps.veille.models import PressItem as _PI
        ctx["veille_preview"] = list(_PI.objects.select_related("blog_cible")[:6])
    except Exception:
        ctx["veille_preview"] = []
    # Workspaces / agents
    try:
        from apps.workspaces.models import Workspace
        ctx["kpi"]["workspaces"] = Workspace.objects.count()
        ctx["workspaces_list"] = list(Workspace.objects.values("name", "slug")[:25])
    except Exception:
        ctx["kpi"]["workspaces"] = "—"
        ctx["workspaces_list"] = []
    return render(request, "dashboard/index.html", ctx)
