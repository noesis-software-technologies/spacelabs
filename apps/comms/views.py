import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.common.ingress_auth import require_ingress_secret

from .models import Message
from .triage import triage


@login_required
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
@require_POST
@require_ingress_secret("COMMS_TG_WEBHOOK_SECRET", "X-Telegram-Bot-Api-Secret-Token")
def telegram_webhook(request):
    """Webhook Telegram : configure ce URL comme webhook du bot pour ingérer les DM."""
    try:
        upd = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)
    if not isinstance(upd, dict):
        return JsonResponse({"ok": False}, status=400)
    msg = upd.get("message", upd.get("edited_message"))
    if msg is None:
        return JsonResponse({"ok": True})  # Other Telegram update types are ignored.
    if not isinstance(msg, dict):
        return JsonResponse({"ok": False}, status=400)
    chat, frm = msg.get("chat"), msg.get("from", {})
    if (not isinstance(chat, dict) or type(chat.get("id")) is not int
            or type(msg.get("message_id")) is not int or msg["message_id"] < 0
            or not isinstance(frm, dict)):
        return JsonResponse({"ok": False}, status=400)
    text = msg.get("text", "")
    if not isinstance(text, str) or any(
        not isinstance(frm.get(key, ""), str) for key in ("username", "first_name", "last_name")
    ):
        return JsonResponse({"ok": False}, status=400)
    sender = (frm.get("username") or f"{frm.get('first_name','')} {frm.get('last_name','')}").strip()
    ext = f"tg-{chat['id']}-{msg['message_id']}"
    if len(ext) > 500:
        return JsonResponse({"ok": False}, status=400)
    prio, needs, cat = triage(sender, "", text)
    # ext_id is unique in the DB; get_or_create handles concurrent deliveries atomically.
    Message.objects.get_or_create(ext_id=ext, defaults={
        "channel": "telegram", "expediteur": sender[:300], "sujet": "",
        "corps": text[:8000], "recu_le": now(), "categorie": cat, "priorite": prio,
        "needs_reply": needs, "statut": "nouveau",
    })
    return JsonResponse({"ok": True})
