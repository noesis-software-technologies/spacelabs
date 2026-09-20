"""Veille AUTO-SOURCÉE pour agentic-pods.com (transformation agentique).

Contrairement à la veille 13-Atmosphère (RP de Thérèse par mail), ici l'agent
**scrape lui-même** les sujets liés à l'univers agentique via Google News RSS
(recherche par requête, sans clé d'API), puis crée des PressItem rattachés au
blog agentic-pods. Le reste du pipeline est identique : veille_draft (rédaction
locale) → veille_publish (même protocole MCP, creds du blog).

Usage :
  python manage.py veille_scrape_agentic --limit 20
  python manage.py veille_scrape_agentic --query "AI agents ROI" --limit 10
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

BLOG_DOMAINE = "agentic-pods.com"
BLOG_NOM = "Agentic Pods"

# Requêtes de sourcing — angle « transformation de l'entreprise dans l'agentique ».
QUERIES = [
    '"agentic AI" (enterprise OR entreprise OR transformation)',
    '"AI agents" (workflow OR automation OR "digital labor")',
    '"agentic" (adoption OR ROI OR gouvernance OR governance)',
    'agentic AI (strategy OR "operating model" OR productivity)',
    # Sujets spécifiques Agentic Pods (demandés par la direction)
    '"type-safe AI" OR "typesafe AI" OR "JEV"',
    '"Weft" ("AI primitives" OR "agent primitives" OR agentic)',
    '"AI primitives" (agents OR agentic OR framework)',
]
TAG_RE = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return TAG_RE.sub("", html or "").strip()


def _rss_url(query: str) -> str:
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "fr", "gl": "FR", "ceid": "FR:fr"})


def _parse_date(s: str):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return now()


class Command(BaseCommand):
    help = "Scrape des sujets agentiques (Google News RSS) → PressItem pour agentic-pods.com."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Nb max d'items à créer")
        parser.add_argument("--query", action="append", default=[], help="Requête additionnelle")

    def handle(self, *args, **o):
        blog, _ = Blog.objects.get_or_create(
            domaine=BLOG_DOMAINE,
            defaults={"nom": BLOG_NOM, "categorie": "agentique", "statut": "actif",
                      "bloc": "Agentic Pods"},
        )
        if not blog.bloc:
            blog.bloc = "Agentic Pods"
            blog.save(update_fields=["bloc"])
        queries = QUERIES + o["query"]
        seen, created, skipped = set(), 0, 0
        for q in queries:
            if created >= o["limit"]:
                break
            try:
                r = requests.get(_rss_url(q), timeout=25,
                                 headers={"User-Agent": "Mozilla/5.0 (veille agentic-pods)"})
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
                mid = "scrape-" + hashlib.md5(link.encode()).hexdigest()[:16]
                if mid in seen or PressItem.objects.filter(message_id=mid).exists():
                    skipped += 1
                    continue
                seen.add(mid)
                src_el = it.find("{*}source")
                source = (src_el.text if src_el is not None else "") or "web"
                desc = _clean(it.findtext("description"))[:1000]
                corps = (f"Sujet repéré dans la veille agentique (source : {source}).\n"
                         f"Titre d'origine : {title}\n{desc}\n\n"
                         f"Angle éditorial agentic-pods : transformation de l'entreprise "
                         f"dans l'univers agentique — enjeux, cas d'usage, gouvernance, ROI.")
                PressItem.objects.create(
                    message_id=mid, expediteur=source, sujet=title[:500],
                    recu_le=_parse_date(it.findtext("pubDate")), categorie="agentique",
                    resume=desc[:500], corps=corps, blog_cible=blog, statut="nouveau",
                    liens_sources=[{"url": link, "texte": source, "kind": "source"}],
                )
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"agentic-pods : {created} sujets créés, {skipped} déjà connus "
            f"(blog #{blog.id} {blog.domaine}). Étape suivante : veille_draft."))
