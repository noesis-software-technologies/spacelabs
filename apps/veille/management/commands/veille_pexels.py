"""Remplit les articles SANS visuel avec des images libres de droit (Pexels).

Requête construite depuis le contexte de l'article (tags → titre → catégorie) →
cohérence image↔article. Télécharge en local (media/veille/<pk>/pexels/), pose la
cover + la galerie + l'alt. N'écrase jamais un article qui a déjà des images.

  python manage.py veille_pexels --dry-run
  python manage.py veille_pexels --per-article 3 --limit 20
"""
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.veille.models import PressItem
from apps.veille.pexels import build_query, search

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class Command(BaseCommand):
    help = "Fallback images libres de droit (Pexels) pour les articles sans visuel."

    def add_arguments(self, parser):
        parser.add_argument("--categorie")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--per-article", type=int, default=3)
        parser.add_argument("--only-drafts", action="store_true", default=True,
                            help="Seulement les articles ayant un brouillon (défaut).")
        parser.add_argument("--force", action="store_true",
                            help="Même si l'article a déjà des images (ajoute en plus).")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--timeout", type=int, default=25)

    def handle(self, *args, **o):
        if not getattr(settings, "PEXELS_API_KEY", ""):
            raise CommandError("PEXELS_API_KEY manquant (mets-le dans .env.local).")

        qs = PressItem.objects.all().order_by("-recu_le", "-id")
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        if o["only_drafts"]:
            qs = qs.filter(draft_statut__in=["brouillon", "valide", "publie"])

        # Sans --force : uniquement ceux qui n'ont AUCUNE image.
        items = [it for it in qs if o["force"] or not it.toutes_images]
        if o["limit"]:
            items = items[: o["limit"]]
        if not items:
            self.stdout.write(self.style.WARNING("Aucun article sans visuel à illustrer."))
            return

        media = Path(settings.MEDIA_ROOT)
        ok = 0
        for it in items:
            q = build_query(it)
            photos = search(q, per_page=o["per_article"])
            line = f"[{it.categorie}] {(it.draft_titre or it.sujet)[:45]} — requête « {q[:40]} » → {len(photos)} photo(s)"
            if o["dry_run"]:
                self.stdout.write(line + " [dry-run]")
                continue
            if not photos:
                self.stdout.write(self.style.WARNING(line + " (aucun résultat)"))
                continue
            dest = media / "veille" / str(it.pk) / "pexels"
            dest.mkdir(parents=True, exist_ok=True)
            local, credits = [], []
            for n, ph in enumerate(photos):
                try:
                    r = requests.get(ph["url"], timeout=o["timeout"])
                    r.raise_for_status()
                except requests.RequestException:
                    continue
                ext = EXT.get(r.headers.get("Content-Type", "").split(";")[0].strip(), ".jpg")
                fname = f"px{n:02d}{ext}"
                (dest / fname).write_bytes(r.content)
                local.append(f"{settings.MEDIA_URL}veille/{it.pk}/pexels/{fname}")
                credits.append(ph["credit"])
            if not local:
                self.stdout.write(self.style.WARNING(line + " (téléchargement échoué)"))
                continue
            it.images_local = (list(it.images_local) + local) if o["force"] else local
            if not it.image_url:
                it.image_url = local[0]
            if not it.image_alt and photos[0].get("alt"):
                it.image_alt = photos[0]["alt"][:300]
            it.save(update_fields=["images_local", "image_url", "image_alt"])
            ok += 1
            self.stdout.write(self.style.SUCCESS(line + f" → {len(local)} en local ({credits[0]})"))

        self.stdout.write(self.style.SUCCESS(f"\n{ok} article(s) illustré(s) via Pexels."))
