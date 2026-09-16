"""Ingestion IMAP de la boîte mail → Message (inbox unifié) + tri automatique.

Identifiants via env (jamais commit) :
    COMMS_IMAP_USER / COMMS_IMAP_PASS  (défaut : VEILLE_IMAP_USER / VEILLE_IMAP_PASS)
    COMMS_IMAP_HOST (défaut imap.gmail.com) · COMMS_IMAP_FOLDER (défaut INBOX)
"""
import email
import imaplib
import os
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import make_aware

from apps.comms.models import Message
from apps.comms.triage import triage


def _dec(s):
    if not s:
        return ""
    return "".join(t.decode(e or "utf-8", "replace") if isinstance(t, bytes) else t
                   for t, e in decode_header(s))


def _plain(msg):
    txt = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attach" not in str(part.get("Content-Disposition")):
                try:
                    txt = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                    break
                except Exception:
                    pass
    else:
        try:
            txt = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
        except Exception:
            pass
    return re.sub(r"\s+", " ", txt).strip()


class Command(BaseCommand):
    help = "Ingestion IMAP de la boîte → Message (inbox unifié) + tri"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        user = os.environ.get("COMMS_IMAP_USER") or os.environ.get("VEILLE_IMAP_USER")
        pw = os.environ.get("COMMS_IMAP_PASS") or os.environ.get("VEILLE_IMAP_PASS")
        host = os.environ.get("COMMS_IMAP_HOST", "imap.gmail.com")
        folder = os.environ.get("COMMS_IMAP_FOLDER", "INBOX")
        if not user or not pw:
            raise CommandError("COMMS_IMAP_USER/PASS (ou VEILLE_IMAP_USER/PASS) manquants")

        M = imaplib.IMAP4_SSL(host)
        M.login(user, pw)
        M.select(folder)
        typ, data = M.search(None, "ALL")
        ids = data[0].split()[-options["limit"]:]
        created = 0
        prio_count = {}
        for i in ids:
            typ, d = M.fetch(i, "(RFC822)")
            msg = email.message_from_bytes(d[0][1])
            mid = (msg.get("Message-ID") or f"uid-{user}-{i.decode()}").strip()
            if Message.objects.filter(ext_id=mid).exists():
                continue
            sender = _dec(msg.get("From"))
            subject = _dec(msg.get("Subject"))
            body = _plain(msg)
            recu = None
            try:
                dt = parsedate_to_datetime(msg.get("Date"))
                recu = dt if dt.tzinfo else make_aware(dt)
            except Exception:
                pass
            prio, needs, cat = triage(sender, subject, body)
            Message.objects.create(
                channel="email", ext_id=mid, expediteur=sender, sujet=subject[:500],
                corps=body[:8000], recu_le=recu, categorie=cat, priorite=prio,
                needs_reply=needs, statut="nouveau",
            )
            created += 1
            prio_count[prio] = prio_count.get(prio, 0) + 1
        M.logout()
        self.stdout.write(self.style.SUCCESS(f"{created} nouveaux messages"))
        for p, n in prio_count.items():
            self.stdout.write(f"  priorité {p}: {n}")
