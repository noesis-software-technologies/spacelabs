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
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import make_aware

from apps.veille.categorize import categorize
from apps.veille.models import Blog, PressItem

_IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif|avif|tiff?)(\?|#|$)", re.I)
_PIXEL = re.compile(r"(pixel|track|/open|beacon|spacer|1x1|/wf/open|utm_)", re.I)
_KIT = re.compile(r"(dropbox|wetransfer|we\.tl|drive\.google|swisstransfer|"
                  r"\.zip|presse|press|media[-_]?kit|galerie|gallery|newsroom)", re.I)
_ATTACH_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "image/gif": ".gif", "image/avif": ".avif", "image/tiff": ".tif"}


def _dec(s):
    if not s:
        return ""
    return "".join(t.decode(e or "utf-8", "replace") if isinstance(t, bytes) else t
                   for t, e in decode_header(s))


def _decode(part):
    try:
        return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    except Exception:
        return ""


def _strip_html(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", html)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&").replace("&eacute;", "é")
           .replace("&egrave;", "è").replace("&agrave;", "à").replace("&#39;", "'")
           .replace("&quot;", '"').replace("&rsquo;", "’"))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", txt)).strip()


def _bodies(msg):
    """Renvoie (texte, html). Fallback : si pas de text/plain, HTML → texte."""
    plain = html = ""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        ct = part.get_content_type()
        if "attach" in str(part.get("Content-Disposition")):
            continue
        if ct == "text/plain" and not plain:
            plain = _decode(part)
        elif ct == "text/html" and not html:
            html = _decode(part)
    text = plain.strip() or _strip_html(html)
    return re.sub(r"[ \t]+", " ", text).strip(), html


def _images(msg, html=""):
    """URLs d'images : <img src>, <a href=…image>, URLs texte en .jpg/png… (hors pixels)."""
    urls = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    blobs = [html] if html else []
    blobs += [_decode(p) for p in parts if p.get_content_type() == "text/html"]
    for blob in blobs:
        for u in re.findall(r'<img[^>]+src=["\']?(https?://[^"\'>\s]+)', blob, re.I):
            urls.append(u)
        for u in re.findall(r'<a[^>]+href=["\']?(https?://[^"\'>\s]+)', blob, re.I):
            if _IMG_EXT.search(u):
                urls.append(u)
    out = []
    for u in urls:
        u = u.rstrip('"\'')
        if u not in out and not _PIXEL.search(u):
            out.append(u)
    return out[:15]


def _links(msg, html=""):
    """Tous les liens externes (avec ancre), + type (kit presse / image / lien)."""
    liens, seen = [], set()
    blobs = [html] if html else []
    blobs += [_decode(p) for p in (msg.walk() if msg.is_multipart() else [msg])
              if p.get_content_type() == "text/html"]
    for blob in blobs:
        for href, texte in re.findall(r'<a[^>]+href=["\']?(https?://[^"\'>\s]+)["\']?[^>]*>(.*?)</a>',
                                      blob, re.I | re.S):
            href = href.rstrip('"\'')
            if href in seen or _PIXEL.search(href):
                continue
            seen.add(href)
            kind = "image" if _IMG_EXT.search(href) else ("kit" if _KIT.search(href) else "lien")
            liens.append({"url": href[:1000],
                          "texte": _strip_html(texte)[:120],
                          "kind": kind})
    return liens[:40]


def _attach_images(msg):
    """Pièces jointes image → [(filename, bytes)]."""
    out = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        ct = part.get_content_type()
        if not ct.startswith("image/"):
            continue
        disp = str(part.get("Content-Disposition") or "")
        if "attachment" not in disp and "inline" not in disp:
            continue
        try:
            data = part.get_payload(decode=True)
        except Exception:
            continue
        if not data:
            continue
        name = _dec(part.get_filename()) or f"img{len(out)}{_ATTACH_EXT.get(ct, '.jpg')}"
        out.append((name, data))
    return out[:15]


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
            corps, html = _bodies(msg)
            imgs = _images(msg, html)
            liens = _links(msg, html)
            attaches = _attach_images(msg)
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
                    corps=corps[:8000],
                    corps_html=html[:100000],
                    liens_sources=liens,
                ),
            )
            # images distantes : ne pas écraser un choix manuel
            if imgs and not obj.images:
                obj.image_url = obj.image_url or imgs[0]
                obj.images = imgs
                obj.save(update_fields=["image_url", "images"])
            # pièces jointes image → sauvegarde locale directe
            if attaches and not obj.images_local:
                dest = Path(settings.MEDIA_ROOT) / "veille" / str(obj.pk)
                dest.mkdir(parents=True, exist_ok=True)
                local = []
                for n, (name, data) in enumerate(attaches):
                    ext = ("." + name.rsplit(".", 1)[-1]) if "." in name else ".jpg"
                    fname = f"att{n:02d}{ext.lower()}"
                    (dest / fname).write_bytes(data)
                    local.append(f"{settings.MEDIA_URL}veille/{obj.pk}/{fname}")
                if local:
                    obj.images_local = local
                    obj.save(update_fields=["images_local"])
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
