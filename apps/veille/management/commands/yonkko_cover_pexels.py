"""Pose des couvertures Pexels thématiques (libres de droit) sur les articles
One Piece déjà poussés qui n'ont pas encore d'image. Générique mais cohérent et
sans copyright (stock, pas d'art officiel). Reprenable via PressItem.cover_url.

Détachable (setsid) + reprenable. Usage :
  python manage.py yonkko_cover_pexels --limit 300
"""
import time

from django.core.management.base import BaseCommand
from apps.veille.models import Blog, PressItem
from apps.veille import mcp, pexels

BLOG_ID = 20

THEMES = [
    (("scan", "chapitre", "manga", "tome"), "manga comic book"),
    (("episode", "épisode", "anime", "trailer", "crunchyroll", "netflix", "série"), "anime convention japan"),
    (("carte", "tcg", "card", "booster", "deck"), "trading card game collection"),
    (("quiz",), "japanese manga reading"),
    (("figurine", "collector", "mcdonald", "goodies", "funko"), "collectible figures toys"),
]
DEFAULT_Q = "japanese manga culture"


def _query(title):
    low = (title or "").lower()
    for kws, q in THEMES:
        if any(k in low for k in kws):
            return q
    return DEFAULT_Q


class Command(BaseCommand):
    help = "Couvertures Pexels thématiques sur les articles One Piece sans image."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=300)

    def handle(self, *args, **o):
        b = Blog.objects.get(id=BLOG_ID)
        qs = (PressItem.objects.filter(categorie="onepiece", cover_url="")
              .exclude(mcp_article_id="").order_by("id")[:o["limit"]])
        cache = {}
        ok = err = 0
        for it in list(qs):
            q = _query(it.sujet)
            pool = cache.get(q)
            if pool is None:
                pool = pexels.search(q, per_page=8) or []
                cache[q] = pool
            if not pool:
                err += 1
                continue
            img = pool[it.id % len(pool)]["url"]
            try:
                r = mcp.rpc("tools/call", {"name": "set_cover_image",
                                           "arguments": {"article_id": int(it.mcp_article_id),
                                                         "image": {"url": img}}},
                            url=b.mcp_url, token=b.mcp_token, timeout=60, retries=2)
                if (r.get("result") or {}).get("isError"):
                    err += 1
                    continue
                it.cover_url = img
                it.save(update_fields=["cover_url"])
                ok += 1
                if ok % 25 == 0:
                    self.stdout.write(f"  … {ok} couvertures posées"); self.stdout.flush()
            except Exception:  # noqa: BLE001
                err += 1
            time.sleep(0.2)
        self.stdout.write(self.style.SUCCESS(f"couvertures: ok {ok} / err {err}"))
