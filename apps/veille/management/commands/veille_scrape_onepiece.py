"""Moisson large One Piece (manga / anime / TCG) pour Yonkko via Google News RSS.

Objectif : constituer un stock d'articles réécrivables (~200+), avec la VRAIE date
(pubDate RSS = rétroactive) et le lien source (pour récupérer l'image plus tard).
Périmètre : One Piece au sens large (chapitres, épisodes, anime, TCG, figurines,
Netflix, quiz), en restant focus One Piece.

Usage :
  python manage.py veille_scrape_onepiece --limit 220
"""
import hashlib
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from apps.veille.models import Blog, PressItem

BLOG_DOMAINE = "yonko.life"
TAG_RE = re.compile(r"<[^>]+>")

QUERIES = [
    '"One Piece" chapitre', '"One Piece" scan', '"One Piece" spoilers',
    '"One Piece" épisode', '"One Piece" anime', '"One Piece" Elbaf',
    '"One Piece" Oda', '"One Piece" Netflix', '"One Piece" live action',
    '"One Piece" théorie', '"One Piece" Luffy', '"One Piece" Zoro',
    '"One Piece" Shanks', '"One Piece" Nika', '"One Piece" Imu',
    '"One Piece Card Game"', '"One Piece" jeu de cartes', '"One Piece" TCG',
    '"One Piece" figurine', '"One Piece" quiz', '"One Piece" manga',
    '"One Piece" trailer', '"One Piece" sortie', '"One Piece" collector',
    '"One Piece" Gear 5', '"One Piece" arc final',
]


def _clean(s):
    return TAG_RE.sub("", s or "").strip()


def _rss(q):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "fr", "gl": "FR", "ceid": "FR:fr"})


def _date(s):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return now()


class Command(BaseCommand):
    help = "Moisson large One Piece (Google News RSS) → PressItem Yonkko."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=220)
        parser.add_argument("--query", action="append", default=[])

    def handle(self, *args, **o):
        blog = Blog.objects.filter(domaine=BLOG_DOMAINE).first() or \
            Blog.objects.filter(bloc="Yonkko", is_principal=False).first()
        if not blog:
            blog, _ = Blog.objects.get_or_create(
                domaine=BLOG_DOMAINE,
                defaults={"nom": "Yonkko", "statut": "actif", "bloc": "Yonkko"})
        seen, created, skipped = set(), 0, 0
        for q in QUERIES + o["query"]:
            if created >= o["limit"]:
                break
            try:
                r = requests.get(_rss(q), timeout=25,
                                 headers={"User-Agent": "Mozilla/5.0 (veille onepiece)"})
                r.raise_for_status()
                items = ET.fromstring(r.content).findall(".//item")
            except (requests.RequestException, ET.ParseError):
                continue
            for it in items:
                if created >= o["limit"]:
                    break
                title = _clean(it.findtext("title"))
                link = (it.findtext("link") or "").strip()
                if not title or not link:
                    continue
                mid = "op-" + hashlib.md5(link.encode()).hexdigest()[:16]
                if mid in seen or PressItem.objects.filter(message_id=mid).exists():
                    skipped += 1
                    continue
                # dédup titre normalisé (évite les quasi-doublons multi-requêtes)
                if PressItem.objects.filter(sujet=title[:500]).exists():
                    skipped += 1
                    continue
                seen.add(mid)
                src_el = it.find("{*}source")
                source = (src_el.text if src_el is not None else "") or "web"
                desc = _clean(it.findtext("description"))[:1000]
                PressItem.objects.create(
                    message_id=mid, expediteur=source, sujet=title[:500],
                    recu_le=_date(it.findtext("pubDate")),
                    publier_le=_date(it.findtext("pubDate")).date(),
                    categorie="onepiece", resume=desc[:500],
                    corps=f"Source : {source}\nTitre : {title}\n{desc}",
                    blog_cible=blog, statut="nouveau",
                    liens_sources=[{"url": link, "texte": source, "kind": "source"}])
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"One Piece : {created} sujets créés, {skipped} déjà connus/doublons "
            f"(blog #{blog.id} {blog.domaine})."))
