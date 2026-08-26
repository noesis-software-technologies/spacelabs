"""Vues UI S-R3 — slots existants uniquement (spec §7) : statusbar + régie.

Aucune cible #content ici : la statusbar se rafraîchit sur elle-même (poll
htmx 4 s, même rythme que le Board), le panneau runs est un fragment inclus
dans la régie.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.workspaces.models import Workspace

from .models import MissionTokenBudget, RunLog


@login_required
def statusbar_fragment(request, slug):
    """Segment `⚡ backend · spent/budget tok` du workspace actif."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)
    last_run = (
        RunLog.objects.filter(mission__workspace=workspace)
        .select_related("backend", "mission")
        .first()  # Meta.ordering = -started_at
    )
    budget = None
    if last_run and last_run.mission_id:
        budget = MissionTokenBudget.objects.filter(mission_id=last_run.mission_id).first()
    return render(
        request,
        "models_routing/_statusbar.html",
        {"last_run": last_run, "budget": budget},
    )


@login_required
def runs_panel(request):
    """Derniers runs routés — colonne régie (backend, tokens, durée, JSONL)."""
    runs = (
        RunLog.objects.filter(mission__workspace__owner=request.user)
        .select_related("backend", "mission")[:15]
    )
    return render(request, "models_routing/_runs_panel.html", {"runs": runs})
