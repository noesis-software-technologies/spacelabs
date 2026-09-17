import json

from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from .models import Message
from .triage import triage


def inbox(request):
    qs = Message.objects.exclude(statut="archive")
    prioritaires = list(qs.filter(priorite="haute")[:40])
    a_traiter = list(qs.filter(needs_reply=True).exclude(priorite="haute")[:40])
    reste = list(qs.filter(needs_reply=False, priorite__in=["normale", "basse"])[:40])
    stats = {
        "total": Message.objects.count(),
        "a_repondre": qs.filter(needs_reply=True).count(),
        "haute": qs.filter(priorite="haute").count(),
        "par_canal": dict(Message.objects.values_list("channel")
                          .annotate(n=Count("id")).values_list("channel", "n")),
    }
    return render(request, "comms/inbox.html", {
        "prioritaires": prioritaires, "a_traiter": a_traiter, "reste": reste, "stats": stats,
        "active_nav": "comms",
    })


@csrf_exempt
def telegram_webhook(request):
    """Webhook Telegram : configure ce URL comme webhook du bot pour ingérer les DM."""
    if request.method != "POST":
        return JsonResponse({"ok": True, "hint": "POST Telegram updates ici"})
    try:
        upd = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False}, status=400)
    msg = upd.get("message") or upd.get("edited_message") or {}
    if msg:
        frm = msg.get("from", {})
        sender = (frm.get("username") or f"{frm.get('first_name','')} {frm.get('last_name','')}").strip()
        text = msg.get("text", "")
        ext = f"tg-{msg.get('chat',{}).get('id')}-{msg.get('message_id')}"
        if not Message.objects.filter(ext_id=ext).exists():
            prio, needs, cat = triage(sender, "", text)
            Message.objects.create(
                channel="telegram", ext_id=ext, expediteur=sender, sujet="",
                corps=text[:8000], recu_le=now(), categorie=cat, priorite=prio,
                needs_reply=needs, statut="nouveau",
            )
    return JsonResponse({"ok": True})
