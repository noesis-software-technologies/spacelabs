"""Renseigne une annonce Vinted : titre/description (générés depuis la photo de
référence selon la méthode du compte) et/ou champs humains (prix, format, état).

Usage :
  python manage.py vinted_set <ref|id> --titre "..." --description "..." [--tags a,b]
  python manage.py vinted_set <ref|id> --prix 25 --format S --etat bon --marque Nike
"""
from django.core.management.base import BaseCommand, CommandError

from apps.vinted.models import ETATS, VintedListing


class Command(BaseCommand):
    help = "Met à jour une annonce Vinted (titre/description générés + champs humains)."

    def add_arguments(self, parser):
        parser.add_argument("id", help="ref (hex) ou id numérique de l'annonce")
        parser.add_argument("--titre")
        parser.add_argument("--description")
        parser.add_argument("--tags", help="csv de mots-clés")
        parser.add_argument("--prix", type=float)
        parser.add_argument("--format", dest="format_colis")
        parser.add_argument("--etat", choices=[e[0] for e in ETATS])
        parser.add_argument("--marque")
        parser.add_argument("--categorie")
        parser.add_argument("--statut")

    def handle(self, *args, **o):
        key = o["id"]
        listing = (VintedListing.objects.filter(ref=key).first()
                   or (VintedListing.objects.filter(pk=key).first() if key.isdigit() else None))
        if not listing:
            raise CommandError(f"Annonce introuvable : {key}")
        fields = []
        for f in ("titre", "description", "format_colis", "marque", "categorie", "statut"):
            if o.get(f) is not None:
                setattr(listing, f, o[f]); fields.append(f)
        if o.get("prix") is not None:
            listing.prix = o["prix"]; fields.append("prix")
        if o.get("etat"):
            listing.etat = o["etat"]; fields.append("etat")
        if o.get("tags"):
            listing.tags = [t.strip() for t in o["tags"].split(",") if t.strip()]; fields.append("tags")
        # statut auto : si titre+description remplis et pas encore publié
        if listing.titre and listing.description and listing.statut == "nouveau":
            listing.statut = "genere"; fields.append("statut")
        if listing.titre and listing.description and listing.prix and listing.etat:
            listing.statut = "pret"; fields.append("statut")
        listing.save()
        self.stdout.write(self.style.SUCCESS(
            f"Annonce #{listing.id} ({listing.ref}) MAJ [{', '.join(sorted(set(fields)))}] "
            f"→ statut {listing.get_statut_display()}"))
        self.stdout.write(f"TITRE: {listing.titre}\nPRIX: {listing.prix} | ÉTAT: {listing.get_etat_display() if listing.etat else '—'} | COLIS: {listing.format_colis or '—'}")
