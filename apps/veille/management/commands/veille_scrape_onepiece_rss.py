"""Moisson One Piece via flux RSS DIRECTS des sites (fix « C ») — vrai lien +
image native (media:content/enclosure), contrairement à Google News qui masque
le lien. Filtre les items One Piece, stocke l'image dans image_url/cover_url pour
que la réécriture pousse une couverture native propre.

Flux vérifiés (exposent lien réel + image) : Dexerto, Gameblog. Extensible via
--feed. Certains sites (Manga-news…) sont derrière Cloudflare et ne répondent pas
au fetch serveur : à ajouter seulement s'ils exposent un flux ouvert.

Usage :
  python manage.py veille_scrape_onepiece_rss
  python manage.py veille_scrape_onepiece_rss --feed https://exemple.fr/feed/
"""
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from apps.veille.models import Blog, PressItem

FEEDS = [
    "https://www.dexerto.fr/feed/",
    "https://gameblog.fr/feed/",
]
TAG_RE = re.compile(r"<[^>]+>")
KEYWORDS = ("one piece", "luffy", "zoro", "eiichiro oda", "elbaf", "gear 5", "wano")


def _clean(s):
    return TAG_RE.sub("", s or "").strip()


def _date(s):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return now()


def _image(item, raw_xml):
    # media:content / media:thumbnail / enclosure / 1er <img> de content:encoded
    for tag in ("{http://search.yahoo.com/mrss/}content",
                "{http://search.yahoo.com/mrss/}thumbnail"):
        el = item.find(tag)
        if el is not None and el.get("url"):
            return el.get("url")
    enc = item.find("enclosure")
    if enc is not None and enc.get("url"):
        return enc.get("url")
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)", raw_xml or "", re.I)
    return m.group(1) if m else ""


class Command(BaseCommand):
    help = "Moisson One Piece via flux RSS directs (lien + image natifs)."

    def add_arguments(self, parser):
        parser.add_argument("--feed", action="append", default=[])
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **o):
        blog = Blog.objects.filter(domaine="yonko.life").first() or Blog.objects.get(id=20)
        created = skipped = 0
        for feed in FEEDS + o["feed"]:
            if created >= o["limit"]:
                break
            try:
                r = requests.get(feed, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                root = ET.fromstring(r.content)
            except (requests.RequestException, ET.ParseError):
                self.stderr.write(f"  flux ignoré : {feed}")
                continue
            for item in root.findall(".//item"):
                if created >= o["limit"]:
                    break
                title = _clean(item.findtext("title"))
                link = (item.findtext("link") or "").strip()
                desc = _clean(item.findtext("description"))
                if not title or not link:
                    continue
                blob = (title + " " + desc).lower()
                if not any(k in blob for k in KEYWORDS):
                    continue  # garder uniquement One Piece
                mid = "oprss-" + hashlib.md5(link.encode()).hexdigest()[:16]
                if PressItem.objects.filter(message_id=mid).exists() or \
                        PressItem.objects.filter(sujet=title[:500]).exists():
                    skipped += 1
                    continue
                raw = ET.tostring(item, encoding="unicode")
                img = _image(item, raw)
                d = _date(item.findtext("pubDate"))
                PressItem.objects.create(
                    message_id=mid, expediteur=feed.split("/")[2], sujet=title[:500],
                    recu_le=d, publier_le=d.date(), categorie="onepiece",
                    resume=desc[:500], corps=f"Source : {link}\n{desc}",
                    image_url=img[:1000], cover_url="", blog_cible=blog, statut="nouveau",
                    liens_sources=[{"url": link, "texte": feed.split('/')[2], "kind": "source"}])
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"RSS direct : {created} sujets One Piece créés (lien+image natifs), {skipped} déjà connus."))
