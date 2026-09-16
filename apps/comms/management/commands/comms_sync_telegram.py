"""Ingestion des DM Telegram (long polling getUpdates) → Message (inbox unifié).

Token via env (jamais commit) : COMMS_TG_TOKEN
Usage : python manage.py comms_sync_telegram   (à lancer en boucle/cron)
"""
import json
import os
import urllib.request

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now, make_aware
from datetime import datetime, timezone as _tz

from apps.comms.models import Message
from apps.comms.triage import triage

OFFSET_FILE = "/tmp/spacelabs_tg_offset"


def _api(token, method, params=""):
    url = f"https://api.telegram.org/bot{token}/{method}{params}"
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.load(r)


class Command(BaseCommand):
    help = "Ingestion des DM Telegram (getUpdates) → inbox comms"

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=0, help="long-poll (s)")

    def handle(self, *args, **options):
        token = os.environ.get("COMMS_TG_TOKEN")
        if not token:
            raise CommandError("COMMS_TG_TOKEN manquant (env)")
        # getUpdates et webhook sont exclusifs → on retire un éventuel webhook
        try:
            _api(token, "deleteWebhook")
        except Exception:
            pass
        offset = None
        if os.path.exists(OFFSET_FILE):
            try:
                offset = int(open(OFFSET_FILE).read().strip()) + 1
            except Exception:
                offset = None
        params = f"?timeout={options['timeout']}"
        if offset:
            params += f"&offset={offset}"
        data = _api(token, "getUpdates", params)
        if not data.get("ok"):
            raise CommandError(f"getUpdates KO: {data}")
        created = 0
        last = None
        for upd in data.get("result", []):
            last = upd["update_id"]
            msg = upd.get("message") or upd.get("edited_message") or {}
            if not msg:
                continue
            frm = msg.get("from", {})
            sender = (frm.get("username") or f"{frm.get('first_name','')} {frm.get('last_name','')}").strip()
            text = msg.get("text") or msg.get("caption") or "[non-texte]"
            ext = f"tg-{upd['update_id']}"
            if Message.objects.filter(ext_id=ext).exists():
                continue
            try:
                recu = make_aware(datetime.fromtimestamp(msg.get("date"))) if msg.get("date") else now()
            except Exception:
                recu = now()
            prio, needs, cat = triage(sender, "", text)
            Message.objects.create(
                channel="telegram", ext_id=ext, expediteur=sender or "inconnu",
                sujet="", corps=text[:8000], recu_le=recu, categorie=cat,
                priorite=prio, needs_reply=needs, statut="nouveau",
            )
            created += 1
        if last is not None:
            open(OFFSET_FILE, "w").write(str(last))
        self.stdout.write(self.style.SUCCESS(f"Telegram: {created} nouveau(x) message(s) ingéré(s)"))
