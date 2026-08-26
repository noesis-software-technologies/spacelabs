"""Observer — la vue spectateur (SSE, anonyme, read-only) et la régie.

Contrat de confidentialité (CDC §5, acceptation S3) :
- un pane PRIVÉ n'expose à l'observateur qu'un placeholder anonyme
  (statut agrégé) — jamais titre, cmd, cwd ni contenu ;
- un pane PUBLIC expose son alias public et son flux EXPURGÉ (redaction
  serveur) — jamais cmd ni cwd ;
- live OFF ⇒ écran d'attente, zéro trame de contenu.

Le SSE est une vue **async** : même boucle d'événements que le PaneManager
et les consumers (daphne), abonnement direct au channel layer.
"""
from __future__ import annotations

import asyncio
import json

from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.common.htmx import render_htmx
from apps.runtime.services.headless_manager import HeadlessManager
from apps.runtime.services.pane_manager import OBSERVER_GROUP, PaneManager
from apps.workspaces.models import Pane

from .forms import RedactionRuleForm
from .models import ObserverSettings, RedactionRule
from .redaction import redactor_for_rules_qs

KEEPALIVE_SECONDS = 15
SSE_RETRY_MS = 2000


# ── Côté spectateur (anonyme, LAN) ─────────────────────────────────────────
def observer_page(request):
    """Page plein écran — aucune donnée sensible dans le HTML : la grille
    arrive par fragment (même filtrage) et le contenu par SSE."""
    return render(request, "observer/observer.html")


OBSERVER_MAX_TILES = 9


def _public_grid_context():
    """Ce que la grille anonyme a le DROIT de contenir. Filtrage unique,
    utilisé par la page ET par le refresh — pas deux chemins à sécuriser."""
    live_owner_ids = list(
        ObserverSettings.objects.filter(live=True).values_list("owner_id", flat=True)
    )
    panes = (
        Pane.objects.filter(workspace__owner_id__in=live_owner_ids)
        .order_by("workspace_id", "order", "id")
    )
    # Plafond de LISIBILITÉ, pas de performance : au-delà de 9 tuiles, la vue
    # télé devient une mosaïque illisible à trois mètres. On montre d'abord ce
    # qui travaille, et on annonce le reste.
    ordered = sorted(panes, key=lambda p: (p.status != Pane.Status.RUNNING, p.workspace_id, p.order, p.pk))
    shown, hidden = ordered[:OBSERVER_MAX_TILES], max(0, len(ordered) - OBSERVER_MAX_TILES)

    items = []
    for pane in shown:
        if pane.is_public:
            items.append({"id": pane.pk, "kind": "public", "pane_kind": pane.kind,
                          "label": pane.public_label, "status": pane.status})
        else:
            # Placeholder : existence + statut, RIEN d'autre.
            items.append({"id": pane.pk, "kind": "private", "pane_kind": pane.kind,
                          "label": "", "status": pane.status})
    return {"live": bool(live_owner_ids), "items": items, "hidden_count": hidden}


def observer_grid(request):
    return render(request, "observer/partials/_grid.html", _public_grid_context())


async def observer_stream(request):
    """Flux SSE : abonnement au groupe observateur + replay public initial.

    Les événements ``stdout`` ne transportent que des données déjà expurgées
    par le PaneManager (le SSE ne voit jamais le buffer privé)."""
    layer = get_channel_layer()
    channel = await layer.new_channel()
    await layer.group_add(OBSERVER_GROUP, channel)
    manager = PaneManager.get()

    def sse(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload)}\n\n"

    async def event_source():
        try:
            yield f"retry: {SSE_RETRY_MS}\n\n"
            # Replay initial : uniquement les buffers PUBLICS des panes
            # diffusables (reconnexion SSE ⇒ l'historique expurgé revient).
            import base64 as b64

            for pane in list(manager.panes.values()):
                replay = manager.replay_public(pane.id)
                if replay:
                    yield sse("stdout", {"pane_id": pane.id, "data": b64.b64encode(replay).decode()})
            for session_id, entry in list(HeadlessManager.get().sessions.items()):
                for item in HeadlessManager.get().replay_events(session_id):
                    yield sse("chat", {"pane_id": session_id, "data": item["event"]})
            while True:
                try:
                    message = await asyncio.wait_for(
                        layer.receive(channel), timeout=KEEPALIVE_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keepalive anti-proxy/anti-timeout
                    continue
                event = message.get("event", "message")
                payload = {k: v for k, v in message.items() if k not in {"type", "event"}}
                yield sse(event, payload)
        finally:
            await layer.group_discard(OBSERVER_GROUP, channel)

    response = StreamingHttpResponse(event_source(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ── Côté régie (opérateur, authentifié) ────────────────────────────────────
@login_required
def regie(request):
    context = {
        "rules": RedactionRule.objects.filter(owner=request.user),
        "form": RedactionRuleForm(),
        "settings_obj": ObserverSettings.for_owner(request.user),
    }
    return render_htmx(request, "observer/regie.html", "observer/partials/_regie_panel.html", context)


async def _refresh_runtime_redactor(user):
    """Vues de règles = async : même boucle que le PaneManager, on peut
    rafraîchir les redactors des panes vivants immédiatement et sans risque."""
    redactor = await redactor_for_rules_async(user)
    PaneManager.get().refresh_redactor(user.pk, redactor)


async def redactor_for_rules_async(user):
    rules = [
        (r.pattern, r.replacement, r.is_regex)
        async for r in RedactionRule.objects.filter(owner=user, is_active=True)
    ]
    from .redaction import compile_redactor

    return compile_redactor(rules)


async def rule_create(request):
    if not await request.auser() or not (await request.auser()).is_authenticated:
        return HttpResponse(status=403)
    user = await request.auser()
    if request.method != "POST":
        return HttpResponse(status=405)
    form = RedactionRuleForm(request.POST)
    if not form.is_valid():
        return render(request, "observer/partials/_rule_form.html", {"form": form}, status=422)
    rule = form.save(commit=False)
    rule.owner = user
    await rule.asave()
    await _refresh_runtime_redactor(user)
    rules = [r async for r in RedactionRule.objects.filter(owner=user)]
    return render(
        request, "observer/partials/_rules_list.html",
        {"rules": rules, "form": RedactionRuleForm()},
    )


async def rule_delete(request, rule_id):
    user = await request.auser()
    if not user.is_authenticated:
        return HttpResponse(status=403)
    if request.method != "POST":
        return HttpResponse(status=405)
    deleted, _ = await RedactionRule.objects.filter(owner=user, pk=rule_id).adelete()
    if not deleted:
        return HttpResponse(status=404)
    await _refresh_runtime_redactor(user)
    return HttpResponse("")
