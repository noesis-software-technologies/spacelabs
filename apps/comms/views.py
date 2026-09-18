import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Message
from .triage import triage


@login_required
@require_POST
def message_reply(request, pk):
    """Génère (ou régénère) un brouillon de réponse IA pour un message."""
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
    """Envoie la réponse (validée) à l'expéditeur, via le canal du message.

    Texte pris dans le POST (`text`) sinon le brouillon IA. Sur succès :
    statut → « repondu ». Envoi explicite (bouton) — jamais automatique.
    """
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
    from .playbooks import PLAYBOOKS
    return render(request, "comms/inbox.html", {
        "prioritaires": prioritaires, "a_traiter": a_traiter, "reste": reste, "stats": stats,
        "active_nav": "comms", "playbooks": PLAYBOOKS,
    })


def _meta_ingest(payload):
    """Parse un payload webhook Meta (WhatsApp + Instagram/Messenger) → Messages."""
    created = 0
    obj = (payload.get("object") or "").lower()
    # object: "instagram" = DM Instagram ; "page" = Messenger ; "whatsapp_business_account" = WA
    msgr = obj == "page"
    chan = "messenger" if msgr else "instagram"
    pfx = "mg" if msgr else "ig"
    for entry in payload.get("entry", []):
        # WhatsApp Cloud API : entry[].changes[].value.messages[]
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
        # Instagram / Messenger : entry[].messaging[]
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
    """Webhook Meta (WhatsApp Cloud API + Instagram/Messenger).

    GET  : vérification (hub.challenge) avec META_VERIFY_TOKEN.
    POST : vérifie X-Hub-Signature-256 (HMAC-SHA256, META_APP_SECRET) puis ingère.
    """
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
