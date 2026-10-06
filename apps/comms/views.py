import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.common.ingress_auth import require_ingress_secret

from .models import Message
from .triage import triage


@login_required
@ensure_csrf_cookie
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


@login_required
@require_POST
def message_reply(request, pk):
    from .reply import suggest_reply
    msg = get_object_or_404(Message, pk=pk)
    reply = suggest_reply(msg)
    if not reply:
        return JsonResponse({"ok": False, "error": "génération indisponible (claude)"}, status=502)
    msg.draft_reply = reply
    msg.reply_at = now()
    msg.save(update_fields=["draft_reply", "reply_at"])
    return JsonResponse({"ok": True, "reply": reply})


@login_required
@require_POST
def message_send(request, pk):
    from .send import send_reply
    msg = get_object_or_404(Message, pk=pk)
    text = (request.POST.get("text") or msg.draft_reply or "").strip()
    if not text:
        return JsonResponse({"ok": False, "error": "aucun texte à envoyer"}, status=400)
    ok, detail = send_reply(msg, text)
    if not ok:
        return JsonResponse({"ok": False, "error": detail}, status=502)
    msg.statut = "repondu"
    msg.save(update_fields=["statut"])
    return JsonResponse({"ok": True, "detail": detail})


def _meta_ingest(payload):
    created = 0
    obj = (payload.get("object") or "").lower()
    msgr = obj == "page"
    chan = "messenger" if msgr else "instagram"
    pfx = "mg" if msgr else "ig"
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            noms = {c.get("wa_id"): (c.get("profile") or {}).get("name", "")
                    for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                frm = m.get("from", "")
                text = (m.get("text") or {}).get("body", "") or m.get("type", "")
                ext = f"wa-{m.get('id')}"
                if Message.objects.filter(ext_id=ext).exists():
                    continue
                prio, needs, cat = triage(noms.get(frm) or frm, "", text)
                Message.objects.create(
                    channel="whatsapp", ext_id=ext, expediteur=noms.get(frm) or frm,
                    sender_id=frm, sujet="", corps=text[:8000], recu_le=now(),
                    categorie=cat, priorite=prio, needs_reply=needs, statut="nouveau")
                created += 1
        for msg in entry.get("messaging", []):
            message = msg.get("message") or {}
            text = message.get("text", "")
            if not text:
                continue
            sender = (msg.get("sender") or {}).get("id", "")
            ext = f"{pfx}-{message.get('mid') or msg.get('timestamp')}"
            if Message.objects.filter(ext_id=ext).exists():
                continue
            prio, needs, cat = triage(sender, "", text)
            Message.objects.create(
                channel=chan, ext_id=ext, expediteur=sender, sender_id=sender, sujet="",
                corps=text[:8000], recu_le=now(), categorie=cat, priorite=prio,
                needs_reply=needs, statut="nouveau")
            created += 1
    return created


@csrf_exempt
def meta_webhook(request):
    import hashlib
    import hmac
    from django.conf import settings
    if request.method == "GET":
        if (request.GET.get("hub.mode") == "subscribe"
                and request.GET.get("hub.verify_token") == settings.META_VERIFY_TOKEN):
            return HttpResponse(request.GET.get("hub.challenge", ""))
        return HttpResponse("forbidden", status=403)
    secret = settings.META_APP_SECRET
    if secret:
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return JsonResponse({"ok": False, "err": "signature"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)
    n = _meta_ingest(payload)
    return JsonResponse({"ok": True, "ingested": n})


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
