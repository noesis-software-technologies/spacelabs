"""Télécharge en local les images des communiqués (pour l'export vers le MCP).

Les images extraites des emails sont des URLs distantes : on les rapatrie dans
MEDIA_ROOT/veille/<pk>/ pour garantir qu'on possède la ref + la galerie au moment
de publier, même si l'URL d'origine expire.

  python manage.py veille_media                 # items avec URLs, pas encore téléchargés
  python manage.py veille_media --force          # re-télécharge tout
  python manage.py veille_media --categorie food
"""
import mimetypes
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.veille.models import PressItem

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
       "image/gif": ".gif", "image/avif": ".avif"}


class Command(BaseCommand):
    help = "Télécharge en local les images des communiqués (ref + galerie)."

    def add_arguments(self, parser):
        parser.add_argument("--categorie")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--timeout", type=int, default=20)

    def handle(self, *args, **o):
        qs = PressItem.objects.all().order_by("-recu_le", "-id")
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        if not o["force"]:
            qs = qs.filter(images_local=[])
        if o["limit"]:
            qs = qs[: o["limit"]]

        media = Path(settings.MEDIA_ROOT)
        total_imgs = ok_items = 0
        for it in qs:
            urls = it.carrousel
            if not urls:
                continue
            dest = media / "veille" / str(it.pk)
            dest.mkdir(parents=True, exist_ok=True)
            local = []
            for n, url in enumerate(urls):
                try:
                    r = requests.get(url, timeout=o["timeout"],
                                     headers={"User-Agent": "SpaceLabs-Veille/1.0"})
                    r.raise_for_status()
                except requests.RequestException:
                    continue
                ext = EXT.get(r.headers.get("Content-Type", "").split(";")[0].strip()) \
                    or mimetypes.guess_extension(r.headers.get("Content-Type", "").split(";")[0]) or ".jpg"
                fname = f"{n:02d}{ext}"
                (dest / fname).write_bytes(r.content)
                local.append(f"{settings.MEDIA_URL}veille/{it.pk}/{fname}")
            if local:
                it.images_local = local
                it.save(update_fields=["images_local"])
                ok_items += 1
                total_imgs += len(local)
                self.stdout.write(self.style.SUCCESS(
                    f"[{it.categorie}] {(it.draft_titre or it.sujet)[:50]} — {len(local)} image(s)"))
        self.stdout.write(self.style.SUCCESS(
            f"\nTerminé : {total_imgs} image(s) sauvegardée(s) sur {ok_items} article(s)."))
