"""Veille auto-sourcée One Piece TCG pour Yonkko (yonko.life).

Scrape des sujets One Piece Card Game (EN/FR/JP) via Google News RSS, dédup,
crée des PressItem rattachés au blog Yonkko. Pipeline aval identique
(veille_draft → veille_publish). Objectif par défaut : ~100 articles.

Usage :
  python manage.py veille_scrape_yonkko --limit 100
  python manage.py veille_scrape_yonkko --query "OP-11 spoilers" --limit 20
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
BLOG_NOM = "Yonkko"

QUERIES = [
    '"One Piece Card Game"',
    '"One Piece TCG"',
    '"One Piece" ("card game" OR TCG) (deck OR decklist OR meta OR tournament)',
    '"One Piece Card Game" (release OR "new set" OR OP-11 OR OP-10 OR OP-12)',
    '"One Piece Card Game" (price OR "alt art" OR "secret rare" OR chase)',
    '"One Piece Card Game" (banlist OR errata OR championship OR "regional")',
    '"One Piece" jeu de cartes',
    '"One Piece" carte (précommande OR display OR booster)',
    "ワンピースカードゲーム",
    "ワンピースカードゲーム (新弾 OR 大会 OR デッキ)",
]
TAG_RE = re.compile(r"<[^>]+>")


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
    help = "Scrape des sujets One Piece TCG (Google News RSS) → PressItem Yonkko."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--query", action="append", default=[])

    def handle(self, *args, **o):
        blog, _ = Blog.objects.get_or_create(
            domaine=BLOG_DOMAINE,
            defaults={"nom": BLOG_NOM, "categorie": "onepiece-tcg",
                      "statut": "actif", "bloc": "Yonkko"})
        if blog.bloc != "Yonkko":
            blog.bloc = "Yonkko"
            blog.save(update_fields=["bloc"])
        seen, created, skipped = set(), 0, 0
        for q in QUERIES + o["query"]:
            if created >= o["limit"]:
                break
            try:
                r = requests.get(_rss(q), timeout=25,
                                 headers={"User-Agent": "Mozilla/5.0 (veille yonkko)"})
                r.raise_for_status()
                items = ET.fromstring(r.content).findall(".//item")
            except (requests.RequestException, ET.ParseError) as e:
                self.stderr.write(f"  requête ignorée ({type(e).__name__}) : {q[:40]}")
                continue
            for it in items:
                if created >= o["limit"]:
                    break
                title = _clean(it.findtext("title"))
                link = (it.findtext("link") or "").strip()
                if not title or not link:
                    continue
                mid = "yk-" + hashlib.md5(link.encode()).hexdigest()[:16]
                if mid in seen or PressItem.objects.filter(message_id=mid).exists():
                    skipped += 1
                    continue
                seen.add(mid)
                src_el = it.find("{*}source")
                source = (src_el.text if src_el is not None else "") or "web"
                desc = _clean(it.findtext("description"))[:1000]
                corps = (f"Sujet One Piece TCG repéré (source : {source}).\n"
                         f"Titre d'origine : {title}\n{desc}\n\n"
                         f"Angle éditorial Yonkko : actualité, méta, decklists, sorties, "
                         f"cotes et collection du One Piece Card Game (FR/EN/JP).")
                PressItem.objects.create(
                    message_id=mid, expediteur=source, sujet=title[:500],
                    recu_le=_date(it.findtext("pubDate")), categorie="onepiece-tcg",
                    resume=desc[:500], corps=corps, blog_cible=blog, statut="nouveau",
                    liens_sources=[{"url": link, "texte": source, "kind": "source"}])
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Yonkko : {created} sujets One Piece TCG créés, {skipped} déjà connus "
            f"(blog #{blog.id} {blog.domaine})."))
