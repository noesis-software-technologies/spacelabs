"""Réaligne la date de publication des brouillons du blog sur leur VRAIE date.

Le pipeline avait daté beaucoup de brouillons sur une date placeholder (souvent
« demain »). Ici on relit la vraie date depuis le PressItem local (champ
`publier_le`, aligné sur la source) et on met à jour `pub_date` du brouillon via
`update_article`. Aucune suppression, aucune activation (la publication reste une
validation humaine dans le calendrier).

DRY-RUN par défaut ; `--apply` exécute.

Usage :
  python manage.py veille_blog_redate --blog 20
  python manage.py veille_blog_redate --blog 20 --apply
  python manage.py veille_blog_redate --blog 20 --only 2026-09-21   # ne traiter que cette date
"""
import re
import time
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from apps.veille.models import Blog, PressItem
from apps.veille import mcp


def _norm(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s)


class Command(BaseCommand):
    help = "Redate les brouillons du blog sur leur vraie date (via update_article). DRY-RUN par défaut."

    def add_arguments(self, parser):
        parser.add_argument("--blog", type=int, required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--only", default="", help="ne traiter que les brouillons à cette pub_date (YYYY-MM-DD)")

    def handle(self, *args, **o):
        b = Blog.objects.filter(id=o["blog"]).first()
        if not b or not b.mcp_token:
            raise CommandError("Blog introuvable ou sans token MCP")

        # vraie date par article_id (depuis le PressItem local) + fallback par titre
        real = {}
        for p in PressItem.objects.exclude(mcp_article_id=""):
            if p.publier_le:
                real[str(p.mcp_article_id)] = p.publier_le.isoformat()
        by_title = {}
        for p in PressItem.objects.all():
            if not p.publier_le:
                continue
            for t in (p.draft_titre, p.seo_title, p.sujet):
                if t:
                    by_title.setdefault(_norm(t), p.publier_le.isoformat())

        # inventaire blog
        after, arts = None, []
        while True:
            args_ = {"status": "all", "limit": 100}
            if after:
                args_["after_id"] = after
            r = mcp.rpc("tools/call", {"name": "list_articles", "arguments": args_},
                        url=b.mcp_url, token=b.mcp_token, timeout=60, retries=4)
            sc = (r.get("result") or {}).get("structuredContent") or {}
            page = sc.get("articles") or []
            arts += page
            after = sc.get("next_after_id")
            if not after or not page:
                break

        plan = []
        for a in arts:
            if a.get("status") != "draft":
                continue
            if o["only"] and a.get("pub_date") != o["only"]:
                continue
            aid = str(a.get("article_id"))
            rd = real.get(aid) or by_title.get(_norm(a.get("title")))
            if rd and rd != a.get("pub_date"):
                plan.append((a["article_id"], a.get("revision", ""), a.get("pub_date"), rd, (a.get("title") or "")[:45]))

        self.stdout.write(f"brouillons: {sum(1 for a in arts if a.get('status')=='draft')} · à redater: {len(plan)}")
        for aid, rev, old, new, t in plan[:10]:
            self.stdout.write(f"  #{aid} {old} -> {new}  {t}")

        if not o["apply"]:
            self.stdout.write(self.style.NOTICE("DRY-RUN — rien modifié (--apply pour exécuter)."))
            return

        ok = err = 0
        for i, (aid, rev, old, new, t) in enumerate(plan, 1):
            try:
                r = mcp.rpc("tools/call",
                            {"name": "update_article",
                             "arguments": {"article_id": aid, "expected_revision": rev, "pub_date": new}},
                            url=b.mcp_url, token=b.mcp_token, timeout=60, retries=3)
                if (r.get("result") or {}).get("isError"):
                    err += 1
                else:
                    ok += 1
            except Exception:  # noqa: BLE001
                err += 1
            if i % 25 == 0:
                self.stdout.write(f"  … {i}/{len(plan)} (ok={ok} err={err})")
                time.sleep(0.3)
        self.stdout.write(self.style.SUCCESS(f"✓ redatés: {ok} · erreurs: {err}"))
