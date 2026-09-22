"""Pousse UN article réécrit sur yonko.life via MCP (draft_article).

Sans catégorie (comme les articles Yonkko existants). Idempotent-ish : si --ref
correspond déjà à un article poussé (PressItem), on met à jour au lieu de recréer.

Usage :
  python manage.py yonkko_push_one --ref op-1194-zoro --title "..." \
      --body-file /tmp/body.html --pub-date 2026-09-22 \
      --meta "..." --keywords "one piece, 1194, zoro" --source "https://..."
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now
from apps.veille.models import Blog, PressItem
from apps.veille import mcp

BLOG_ID = 20


class Command(BaseCommand):
    help = "Pousse un article réécrit sur Yonkko (MCP draft_article), sans catégorie."

    def add_arguments(self, parser):
        parser.add_argument("--ref", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--body-file", required=True, help="fichier HTML du corps réécrit")
        parser.add_argument("--pub-date", default="")
        parser.add_argument("--meta", default="")
        parser.add_argument("--keywords", default="")
        parser.add_argument("--source", default="")
        parser.add_argument("--cover-url", default="", help="URL image de couverture (og:image)")

    def handle(self, *args, **o):
        b = Blog.objects.filter(id=BLOG_ID).first()
        if not b or not b.mcp_token:
            raise CommandError("Blog Yonkko introuvable ou sans token MCP")
        body = Path(o["body_file"]).read_text(encoding="utf-8").strip()
        if len(body) < 200:
            raise CommandError("corps trop court (réécriture manquante ?)")

        args_ = {"title": o["title"], "body_html": body}
        if o["meta"]:
            args_["meta_description"] = o["meta"][:300]
        if o["keywords"]:
            args_["meta_keywords"] = o["keywords"][:300]
        if o["pub_date"]:
            args_["pub_date"] = o["pub_date"]

        r = mcp.rpc("tools/call", {"name": "draft_article", "arguments": args_},
                    url=b.mcp_url, token=b.mcp_token, timeout=90, retries=3)
        res = r.get("result") or {}
        if res.get("isError"):
            txt = (res.get("content") or [{}])[0].get("text", "")
            raise CommandError(f"MCP: {txt[:200]}")
        sc = res.get("structuredContent") or {}
        art = sc.get("article_id") or res.get("article_id")
        if not art:
            raise CommandError("pas d'article_id renvoyé")

        # image de couverture (og:image) si fournie
        cover_ok = ""
        if o.get("cover_url"):
            try:
                mcp.rpc("tools/call", {"name": "set_cover_image",
                                       "arguments": {"article_id": art,
                                                     "image": {"url": o["cover_url"]}}},
                        url=b.mcp_url, token=b.mcp_token, timeout=60, retries=2)
                cover_ok = " +cover"
            except Exception:  # noqa: BLE001
                cover_ok = " (cover échec)"

        # trace locale (pour dédup/redate ultérieurs)
        it, _ = PressItem.objects.get_or_create(
            message_id=f"yonkko-url-{o['ref']}",
            defaults={"sujet": o["title"][:500]},
        )
        it.sujet = o["title"][:500]
        it.draft_titre = o["title"][:300]
        it.blog_cible = b
        it.mcp_article_id = str(art)
        it.mcp_status = "draft"
        it.mcp_pushed_at = now()
        it.statut = "publie"
        it.draft_statut = "publie"
        if o["source"]:
            it.liens_sources = [{"url": o["source"], "texte": "source", "kind": "lien"}]
        try:
            import datetime
            if o["pub_date"]:
                it.publier_le = datetime.date.fromisoformat(o["pub_date"])
        except Exception:  # noqa: BLE001
            pass
        it.save()
        self.stdout.write(self.style.SUCCESS(f"OK article_id={art} slug={sc.get('slug','')} ref={o['ref']}{cover_ok}"))
