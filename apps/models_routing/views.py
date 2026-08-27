"""Vues UI S-R3 — slots existants uniquement (spec §7) : statusbar + régie.

Aucune cible #content ici : la statusbar se rafraîchit sur elle-même (poll
htmx 4 s, même rythme que le Board), le panneau runs est un fragment inclus
dans la régie.
"""
import json
import time

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.workspaces.models import Workspace

from .models import GlobalBudget, MissionTokenBudget, OpenclawExchangeLog, RunLog


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


@login_required
def openclaw_stats(request):
    """Stats budgétaires Telegram/OpenClaw — JSON ou HTML selon Accept."""
    from django.db.models import Sum, Count
    budget = GlobalBudget.get()
    daily = OpenclawExchangeLog.daily_totals()
    weekly = OpenclawExchangeLog.weekly_totals()

    daily_cap = budget.daily_cap_tokens
    daily_pct = round(daily["total"] / daily_cap * 100, 2) if daily_cap else 0
    weekly_pct = round(weekly["total"] / budget.weekly_tokens * 100, 2) if budget.weekly_tokens else 0

    recent = list(
        OpenclawExchangeLog.objects.values(
            "created_at", "model_id", "prompt_tokens", "completion_tokens", "session_id", "channel"
        ).order_by("-created_at")[:30]
    )

    # Sessions regroupées par session_id avec cumul tokens
    sessions = list(
        OpenclawExchangeLog.objects.values("session_id", "channel")
        .annotate(
            exchanges=Count("id"),
            total_prompt=Sum("prompt_tokens"),
            total_completion=Sum("completion_tokens"),
            last_at=models.Max("created_at"),
        )
        .order_by("-last_at")[:15]
    )

    data = {
        "budget": {
            "weekly_tokens": budget.weekly_tokens,
            "daily_cap_tokens": daily_cap,
            "daily_cap_pct": float(budget.daily_cap_pct),
            "note": budget.note,
        },
        "today": {**daily, "cap_pct_used": daily_pct},
        "week": {**weekly, "weekly_pct_used": weekly_pct},
        "remaining_today": max(0, daily_cap - daily["total"]),
        "recent": recent,
        "sessions": sessions,
    }

    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(data, default=str)

    return render(request, "models_routing/_openclaw_stats.html", {"stats": data})


@login_required
def openclaw_stats_stream(request):
    """SSE — pousse les stats budget toutes les 5 s au navigateur."""
    def event_stream():
        while True:
            budget = GlobalBudget.get()
            daily = OpenclawExchangeLog.daily_totals()
            weekly = OpenclawExchangeLog.weekly_totals()
            daily_cap = budget.daily_cap_tokens
            payload = {
                "daily_total": daily["total"],
                "daily_pct": round(daily["total"] / daily_cap * 100, 2) if daily_cap else 0,
                "daily_cap": daily_cap,
                "weekly_total": weekly["total"],
                "weekly_pct": round(weekly["total"] / budget.weekly_tokens * 100, 2) if budget.weekly_tokens else 0,
                "weekly_cap": budget.weekly_tokens,
                "remaining_today": max(0, daily_cap - daily["total"]),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(5)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_POST
def openclaw_log_exchange(request):
    """Endpoint interne — enregistre un échange OpenClaw (appelé par le runtime)."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    OpenclawExchangeLog.objects.create(
        channel=payload.get("channel", "telegram"),
        session_id=payload.get("session_id", ""),
        message_id=payload.get("message_id", ""),
        model_id=payload.get("model_id", "claude-sonnet-4-6"),
        prompt_tokens=int(payload.get("prompt_tokens", 0)),
        completion_tokens=int(payload.get("completion_tokens", 0)),
    )
    return JsonResponse({"status": "ok"})
