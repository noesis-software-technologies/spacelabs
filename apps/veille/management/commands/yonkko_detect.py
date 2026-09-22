"""Audit « trace IA » local (détecteur maison) sur les articles Yonkko.

Score chaque article (0 humain -> 100 ia) et liste ceux à re-humaniser.
Usage :
  python manage.py yonkko_detect --recent 50
  python manage.py yonkko_detect --ids 649,650
  python manage.py yonkko_detect --recent 200 --flag 45   # liste les > seuil
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from apps.veille.models import Blog, PressItem
from apps.veille import mcp, detector

BLOG_ID = 20


class Command(BaseCommand):
    help = "Audit détecteur IA maison sur les articles Yonkko."

    def add_arguments(self, parser):
        parser.add_argument("--ids", default="")
        parser.add_argument("--recent", type=int, default=0)
        parser.add_argument("--flag", type=int, default=60, help="seuil au-dessus duquel signaler")

    def handle(self, *args, **o):
        b = Blog.objects.get(id=BLOG_ID)
        ids = [x.strip() for x in o["ids"].split(",") if x.strip()]
        if o["recent"]:
            ids = [p.mcp_article_id for p in
                   PressItem.objects.exclude(mcp_article_id="").order_by("-mcp_pushed_at")[:o["recent"]]]
        if not ids:
            raise CommandError("préciser --ids ou --recent")
        verdicts, flagged = Counter(), []
        for aid in ids:
            try:
                g = mcp.rpc("tools/call", {"name": "get_article", "arguments": {"article_id": int(aid)}},
                            url=b.mcp_url, token=b.mcp_token, timeout=40, retries=2)
                body = ((g.get("result") or {}).get("structuredContent") or {}).get("body_html", "")
            except Exception:  # noqa: BLE001
                continue
            if not body:
                continue
            s = detector.score(body)
            verdicts[s["verdict"]] += 1
            if s["score"] >= o["flag"]:
                flagged.append((aid, s["score"]))
        self.stdout.write(f"audité: {sum(verdicts.values())} | " + " ".join(f"{k}={v}" for k, v in verdicts.items()))
        if flagged:
            self.stdout.write(self.style.WARNING(f"à re-humaniser (>= {o['flag']}) : "
                              + ", ".join(f"#{a}({s})" for a, s in flagged)))
        else:
            self.stdout.write(self.style.SUCCESS(f"aucun article >= {o['flag']} — RAS"))
