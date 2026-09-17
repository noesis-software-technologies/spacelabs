"""Dashboard central SpaceLabs (hub) — KPIs live + accès modules."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def spacelabs_workspaces(request):
    """Liste des workspaces au design dashboard (extends dashboard/shell.html)."""
    ctx = {"active_nav": "workspaces", "workspaces_rows": []}
    try:
        from apps.workspaces.models import Workspace
        qs = Workspace.objects.all() if request.user.is_superuser \
            else Workspace.objects.for_owner(request.user)
        from decimal import Decimal

        from django.db.models import Count, Sum

        from apps.ops.models import SessionTrace
        conso = {r["workspace"]: r for r in SessionTrace.objects.values("workspace").annotate(
            cost=Sum("cost_usd"), tout=Sum("tokens_out"), sessions=Sum("sessions"), n=Count("id"))}
        rows = []
        for w in qs:
            try:
                n_panes = w.panes.filter(is_system=False).count()
            except Exception:
                n_panes = 0
            c = conso.get(w.pk, {})
            rows.append({"name": w.name, "slug": w.slug,
                         "cwd": getattr(w, "cwd", ""), "panes": n_panes,
                         "owner": getattr(getattr(w, "owner", None), "username", ""),
                         "cost": c.get("cost") or Decimal("0"), "tokens": c.get("tout") or 0,
                         "sessions": c.get("sessions") or 0, "traces": c.get("n") or 0})
        ctx["workspaces_rows"] = rows
        # workspaces_list alimente aussi la sidebar (prepend) du shell
        ctx["workspaces_list"] = [{"name": r["name"], "slug": r["slug"]} for r in rows][:25]
    except Exception:
        pass
    return render(request, "dashboard/workspaces.html", ctx)


@login_required
def spacelabs_usage(request):
    """Journal « Sessions & consommation » : tokens/coûts/sessions par projet."""
    from decimal import Decimal

    from django.db.models import Count, Sum

    from apps.ops.models import SessionTrace
    traces = list(SessionTrace.objects.select_related("workspace"))
    # Agrégat par projet
    projets = {}
    for t in traces:
        p = projets.setdefault(t.projet, {
            "projet": t.projet, "cost": Decimal("0"), "tin": 0, "tout": 0,
            "sessions": 0, "conversations": 0, "lignes": [],
        })
        p["cost"] += t.cost_usd or 0
        p["tin"] += t.tokens_in
        p["tout"] += t.tokens_out
        p["sessions"] += t.sessions
        p["conversations"] += t.conversations
        p["lignes"].append(t)
    projets = sorted(projets.values(), key=lambda x: -x["cost"])
    agg = SessionTrace.objects.aggregate(
        cost=Sum("cost_usd"), tin=Sum("tokens_in"), tout=Sum("tokens_out"),
        sessions=Sum("sessions"), conversations=Sum("conversations"), n=Count("id"))
    return render(request, "dashboard/usage.html", {
        "active_nav": "usage", "projets": projets, "agg": agg,
    })


@login_required
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
