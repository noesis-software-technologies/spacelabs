"""Publie les brouillons vers le MCP de 13 Atmosphère (JSON-RPC).

draft_article → set_cover_image → add_carousel_images. On ne crée que des
**brouillons** : la publication finale reste une validation humaine côté blog.

Sûr par défaut : **dry-run**. Ajoute --send pour émettre.

  python manage.py veille_publish --status valide --dry-run
  python manage.py veille_publish --status valide --send --limit 5
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.veille import mcp
from apps.veille.models import PressItem


class Command(BaseCommand):
    help = "Publie les brouillons vers le MCP 13 Atmosphère (dry-run par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("--status", default="valide")
        parser.add_argument("--categorie")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--send", action="store_true", help="Émet réellement (sinon dry-run).")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-images", action="store_true")
        parser.add_argument("--timeout", type=int, default=60)

    def handle(self, *args, **o):
        from django.conf import settings
        statuses = [s.strip() for s in o["status"].split(",") if s.strip()]
        qs = PressItem.objects.filter(draft_statut__in=statuses).exclude(draft_corps="")
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        qs = qs.order_by("publier_le", "categorie", "id")
        if o["limit"]:
            qs = qs[: o["limit"]]
        items = list(qs)
        if not items:
            self.stdout.write(self.style.WARNING("Aucun brouillon à publier pour ce filtre."))
            return
        if o["send"] and not settings.ATMOSPHERE_MCP_TOKEN:
            raise CommandError("ATMOSPHERE_MCP_TOKEN manquant (mets-le dans .env.local).")

        ok = 0
        for it in items:
            args = mcp.payload(it)
            self.stdout.write(f"\n=== [{it.categorie}] {args['title'][:60]} ===")
            if not o["send"]:
                self.stdout.write(json.dumps(
                    {**args, "body_html": args["body_html"][:120] + "…"}, ensure_ascii=False, indent=2))
                self.stdout.write(f"  + cover: {it.image_ref or '—'} | carrousel: {len(it.carrousel)} image(s)")
                continue
            res = mcp.publish_item(it, with_images=not o["no_images"], timeout=o["timeout"])
            if res["ok"]:
                ok += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  → brouillon MCP créé (article_id={res['article_id']}, {res.get('images', 0)} image(s))"))
                if res.get("warning"):
                    self.stdout.write(self.style.WARNING(f"  ⚠ {res['warning']}"))
            else:
                self.stdout.write(self.style.ERROR(f"  échec : {res['error']}"))

        if o["send"]:
            self.stdout.write(self.style.SUCCESS(
                f"\n{ok}/{len(items)} brouillon(s) créé(s). Validation humaine sur /administration/calendar/."))
        else:
            self.stdout.write(self.style.WARNING(f"\n[DRY-RUN] {len(items)} article(s) prêts. --send pour émettre."))
