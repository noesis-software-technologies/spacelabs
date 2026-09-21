"""Dédoublonnage CÔTÉ BLOG via MCP.

Énumère les articles avec `list_articles` (fiable, fournit `revision`), regroupe
par titre normalisé, GARDE un article par groupe (le publié / le plus ancien id)
et supprime les brouillons perdants avec `delete_article`.

Règle : le publié prime et n'est jamais supprimé (delete_article refuse les
non-brouillons de toute façon). Les doublons dont le perdant est publié sont
signalés à part (non supprimables automatiquement).

DRY-RUN par défaut ; `--apply` supprime. Reprise possible (idempotent).

Usage :
  python manage.py veille_blog_dedup --blog 20
  python manage.py veille_blog_dedup --blog 20 --apply
"""
import re
import time
import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from apps.veille.models import Blog
from apps.veille import mcp


def norm(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s)


class Command(BaseCommand):
    help = "Dédoublonne les articles du blog via MCP (le publié prime). DRY-RUN par défaut."

    def add_arguments(self, parser):
        parser.add_argument("--blog", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def _all_articles(self, b):
        after, out = None, []
        while True:
            args = {"status": "all", "limit": 100}
            if after:
                args["after_id"] = after
            r = mcp.rpc("tools/call", {"name": "list_articles", "arguments": args},
                        url=b.mcp_url, token=b.mcp_token, timeout=60, retries=4)
            sc = (r.get("result") or {}).get("structuredContent") or {}
            page = sc.get("articles") or []
            out += page
            after = sc.get("next_after_id")
            if not after or not page:
                break
        return out

    def handle(self, *args, **o):
        b = Blog.objects.filter(id=o["blog"]).first()
        if not b or not b.mcp_token:
            raise CommandError("Blog introuvable ou sans token MCP")

        arts = self._all_articles(b)
        g = defaultdict(list)
        for a in arts:
            g[norm(a.get("title"))].append(a)
        dups = {k: v for k, v in g.items() if len(v) > 1}

        to_delete = []   # (id, revision, title)
        conflicts = []   # doublons publiés non supprimables
        for v in dups.values():
            pub = [a for a in v if a.get("status") == "published"]
            keep = (sorted(pub, key=lambda a: a["article_id"])[0] if pub
                    else sorted(v, key=lambda a: a["article_id"])[0])
            for a in v:
                if a["article_id"] == keep["article_id"]:
                    continue
                if a.get("status") == "draft":
                    to_delete.append((a["article_id"], a.get("revision", ""), (a.get("title") or "")[:50]))
                else:
                    conflicts.append((a["article_id"], a.get("title") or ""))

        self.stdout.write(f"articles: {len(arts)} · groupes doublons: {len(dups)}")
        self.stdout.write(f"brouillons supprimables: {len(to_delete)} · conflits publiés: {len(conflicts)}")
        if conflicts:
            self.stdout.write(self.style.WARNING("Doublons PUBLIÉS (à traiter à la main) :"))
            for aid, t in conflicts[:15]:
                self.stdout.write(f"  #{aid} {t[:60]}")

        if not o["apply"]:
            self.stdout.write(self.style.NOTICE("DRY-RUN — rien supprimé (--apply pour exécuter)."))
            return

        ok = err = 0
        for i, (aid, rev, t) in enumerate(to_delete, 1):
            try:
                r = mcp.rpc("tools/call",
                            {"name": "delete_article", "arguments": {"article_id": aid, "expected_revision": rev}},
                            url=b.mcp_url, token=b.mcp_token, timeout=60, retries=3)
                if (r.get("result") or {}).get("isError"):
                    err += 1
                else:
                    ok += 1
            except Exception:  # noqa: BLE001
                err += 1
            if i % 25 == 0:
                self.stdout.write(f"  … {i}/{len(to_delete)} (ok={ok} err={err})")
                time.sleep(0.3)
        self.stdout.write(self.style.SUCCESS(f"✓ supprimés: {ok} · erreurs: {err}"))
