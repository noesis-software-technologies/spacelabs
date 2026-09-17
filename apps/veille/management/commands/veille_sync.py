"""Ingestion des communiqués transférés par Thérèse (IMAP) → PressItem, catégorisés + dispatchés.

Identifiants via variables d'environnement (jamais en dur / jamais commit) :
    VEILLE_IMAP_USER   (ex: spacelabs.ai.pro@gmail.com)
    VEILLE_IMAP_PASS   (mot de passe d'application Gmail)
    VEILLE_IMAP_HOST   (défaut imap.gmail.com)
    VEILLE_IMAP_FROM   (défaut: therese)   -> filtre Gmail from:<...>

Usage : python manage.py veille_sync
"""
import email
import imaplib
import os
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import make_aware

from apps.veille.categorize import categorize
from apps.veille.models import Blog, PressItem


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


def _images(msg):
    """Extrait les URLs d'images des parties HTML (hors pixels de tracking)."""
    urls = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() != "text/html":
            continue
        try:
            html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        for u in re.findall(r'<img[^>]+src=["\']?(https?://[^"\'>\s]+)', html, flags=re.I):
            if u not in urls:
                urls.append(u)
    urls = [u for u in urls if not re.search(r"(pixel|track|/open|beacon|spacer|1x1)", u, re.I)]
    return urls[:12]


class Command(BaseCommand):
    help = "Ingestion IMAP des communiqués de Thérèse → PressItem catégorisés"

    def add_arguments(self, parser):
        parser.add_argument("--folder", default='"[Gmail]/Tous les messages"')
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **options):
        user = os.environ.get("VEILLE_IMAP_USER")
        pw = os.environ.get("VEILLE_IMAP_PASS")
        host = os.environ.get("VEILLE_IMAP_HOST", "imap.gmail.com")
        frm = os.environ.get("VEILLE_IMAP_FROM", "therese")
        if not user or not pw:
            raise CommandError("VEILLE_IMAP_USER / VEILLE_IMAP_PASS manquants (env)")

        blogs = {b.categorie: b for b in Blog.objects.all()}
        principal = Blog.objects.filter(is_principal=True).first()

        M = imaplib.IMAP4_SSL(host)
        M.login(user, pw)
        M.select(options["folder"])
        typ, data = M.search(None, "X-GM-RAW", f"from:{frm}")
        ids = data[0].split()[-options["limit"]:]
        created = updated = 0
        by_cat = {}
        for i in ids:
            typ, d = M.fetch(i, "(RFC822)")
            msg = email.message_from_bytes(d[0][1])
            mid = (msg.get("Message-ID") or f"uid-{i.decode()}").strip()
            sujet = _dec(msg.get("Subject")).replace("Fwd:", "").replace("Fwd :", "").strip()
            corps = _plain(msg)
            imgs = _images(msg)
            cat = categorize(sujet, corps)
            recu = None
            try:
                dt = parsedate_to_datetime(msg.get("Date"))
                recu = dt if dt.tzinfo else make_aware(dt)
            except Exception:
                pass
            cible = blogs.get(cat) or principal
            obj, is_new = PressItem.objects.update_or_create(
                message_id=mid,
                defaults=dict(
                    expediteur=_dec(msg.get("From")),
                    sujet=sujet[:500],
                    recu_le=recu,
                    categorie=cat,
                    resume=corps[:280],
                    corps=corps[:5000],
                ),
            )
            # images : ne pas écraser un choix manuel
            if imgs and not obj.images:
                obj.image_url = obj.image_url or imgs[0]
                obj.images = imgs
                obj.save(update_fields=["image_url", "images"])
            # n'écrase pas un dispatch manuel déjà fait
            if is_new or obj.blog_cible is None:
                obj.blog_cible = cible
                if obj.statut == "nouveau":
                    obj.statut = "assigne"
                obj.save(update_fields=["blog_cible", "statut"])
            created += int(is_new)
            updated += int(not is_new)
            by_cat[cat] = by_cat.get(cat, 0) + 1
        M.logout()

        self.stdout.write(self.style.SUCCESS(f"{created} nouveaux, {updated} mis à jour"))
        for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {cat:12} : {n}")
