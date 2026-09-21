"""Intake Vinted : reçoit N photos, choisit la plus lisible comme référence,
crée l'annonce. (Le titre/description sont générés ensuite depuis la référence
selon la méthode du compte ; prix/format/état fournis par l'humain.)

Usage :
  python manage.py vinted_ingest --dir /chemin/dossier_photos
  python manage.py vinted_ingest --img a.jpg --img b.jpg [--prix 25 --etat bon --format S]
"""
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.vinted.models import VintedListing
from apps.vinted.reference import pick_reference

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


class Command(BaseCommand):
    help = "Crée une annonce Vinted à partir de N photos (choisit la référence la plus lisible)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", help="Dossier contenant les photos")
        parser.add_argument("--img", action="append", default=[], help="Chemin d'une photo (répétable)")
        parser.add_argument("--prix", type=float)
        parser.add_argument("--format", dest="format_colis", default="")
        parser.add_argument("--etat", default="")

    def handle(self, *args, **o):
        srcs = list(o["img"])
        if o["dir"]:
            d = Path(o["dir"])
            if not d.is_dir():
                raise CommandError(f"Dossier introuvable : {d}")
            srcs += [str(p) for p in sorted(d.iterdir()) if p.suffix.lower() in EXTS]
        srcs = [s for s in srcs if Path(s).exists()]
        if not srcs:
            raise CommandError("Aucune photo fournie (--dir ou --img).")

        ref = uuid.uuid4().hex[:12]
        dest = Path(settings.MEDIA_ROOT) / "vinted" / ref
        dest.mkdir(parents=True, exist_ok=True)
        stored = []
        for n, s in enumerate(srcs):
            ext = Path(s).suffix.lower() or ".jpg"
            out = dest / f"img{n:02d}{ext}"
            shutil.copyfile(s, out)
            stored.append(str(out))
        reference = pick_reference(stored)

        listing = VintedListing.objects.create(
            ref=ref, images=stored, reference_image=reference,
            prix=o["prix"], format_colis=o["format_colis"], etat=o["etat"],
            statut="nouveau")
        self.stdout.write(self.style.SUCCESS(
            f"Annonce #{listing.id} (ref {ref}) — {len(stored)} photo(s), "
            f"référence : {Path(reference).name if reference else '—'}. "
            f"Étape suivante : générer titre/description depuis la référence."))
        self.stdout.write(f"REFERENCE_PATH={reference}")
