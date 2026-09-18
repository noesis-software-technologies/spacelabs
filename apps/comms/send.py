"""Envoi sortant des réponses (validées) vers les canaux Meta.

Router par canal : WhatsApp Cloud API / Messenger (Page) / Instagram DM.
Tout envoi est déclenché explicitement par l'utilisateur (bouton « Envoyer »)
après validation du brouillon — jamais en automatique.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings


def _graph_post(path, token, payload):
    url = f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/{path}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return True, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {"error": str(e)}
        return False, body
    except Exception as e:  # noqa: BLE001
        return False, {"error": str(e)}


def send_reply(msg, text):
    """Envoie `text` à l'expéditeur de `msg` selon son canal.

    Retourne (ok: bool, detail: dict). Ne dépend que de tokens en settings
    (.env.local) ; renvoie une erreur claire si le token manque.
    """
    to = (msg.sender_id or msg.expediteur or "").strip()
    if not to:
        return False, {"error": "destinataire introuvable (sender_id manquant)"}
    ch = msg.channel

    if ch == "whatsapp":
        token, pid = settings.WHATSAPP_TOKEN, settings.WHATSAPP_PHONE_ID
        if not (token and pid):
            return False, {"error": "WHATSAPP_TOKEN / WHATSAPP_PHONE_ID manquants (.env.local)"}
        return _graph_post(f"{pid}/messages", token, {
            "messaging_product": "whatsapp", "to": to,
            "type": "text", "text": {"body": text}})

    if ch == "messenger":
        token = settings.META_PAGE_TOKEN
        if not token:
            return False, {"error": "META_PAGE_TOKEN manquant (.env.local)"}
        return _graph_post("me/messages", token, {
            "recipient": {"id": to}, "messaging_type": "RESPONSE",
            "message": {"text": text}})

    if ch == "instagram":
        token = settings.META_IG_TOKEN or settings.META_PAGE_TOKEN
        if not token:
            return False, {"error": "META_IG_TOKEN manquant (.env.local)"}
        return _graph_post("me/messages", token, {
            "recipient": {"id": to}, "message": {"text": text}})

    return False, {"error": f"canal '{ch}' non pris en charge pour l'envoi"}
