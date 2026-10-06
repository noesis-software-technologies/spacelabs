"""Peuple BoutiqueProduct depuis les StockItems de l'entrepôt.

Usage :
  python manage.py populate_boutique          # crée/met à jour
  python manage.py populate_boutique --reset  # supprime tout et recrée
"""
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.carreaux.models import BoutiqueProduct
from apps.vinted.models import StockItem

DESCRIPTIONS = {
    "pikachu": "Pikachu iconique issu du set {set}. Carte en excellent état, {condition}. Un incontournable pour tout collectionneur Pokémon.",
    "display": "Display scellé {nom}. Idéal pour l'ouverture ou la revente. État : {condition}.",
    "coffret": "Coffret collector {nom}. Contenu complet, {condition}. Parfait pour offrir ou compléter une collection.",
    "mewtwo": "Mewtwo légendaire — {nom}. Illustration rare très recherchée des collectionneurs. État : {condition}.",
    "mew": "Mew mystérieux — {nom}. Carte de collection prisée, difficile à trouver. État : {condition}.",
    "gradé": "{nom}. Carte gradée par un professionnel, authenticité garantie. Grade et état vérifiés.",
    "promo": "Carte promo exclusive — {nom}. Édition limitée, état {condition}.",
    "_default": "{nom}. Carte de collection Pokémon en excellent état. Idéale pour jouer ou collectionner.",
}


def _description(item):
    nom = item.nom
    nom_lower = nom.lower()
    condition = "loose (non gradée)" if "loose" in nom_lower else ("PSA gradée" if "psa" in nom_lower else "non gradée")
    set_name = ""
    if "30th" in nom_lower or "m6a" in nom_lower:
        set_name = "M6A 30th Celebration"
    elif "rocket" in nom_lower:
        set_name = "Team Rocket"
    elif "storm" in nom_lower:
        set_name = "Storm Emeralda"

    ctx = {"nom": nom, "condition": condition, "set": set_name or "collection spéciale"}

    for key, tpl in DESCRIPTIONS.items():
        if key == "_default":
            continue
        if key in nom_lower:
            return tpl.format(**ctx)
    return DESCRIPTIONS["_default"].format(**ctx)


def _titre(item):
    nom = item.nom
    if len(nom) <= 70:
        return nom
    return nom[:67] + "…"


def _slug(titre, pk):
    base = slugify(titre)[:180]
    slug = base
    n = 1
    while BoutiqueProduct.objects.filter(slug=slug).exclude(stock_item_id=pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Command(BaseCommand):
    help = "Crée/met à jour les BoutiqueProduct depuis les StockItems avec prix_achat."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Supprime et recrée tout")

    def handle(self, *args, **o):
        if o["reset"]:
            deleted, _ = BoutiqueProduct.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"{deleted} produit(s) supprimé(s)."))

        items = StockItem.objects.filter(
            prix_achat__isnull=False,
        ).exclude(statut__in=["vendu", "vendu_en_cours"])

        created = updated = skipped = 0
        for item in items:
            pv = (item.prix_achat * Decimal("1.35")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            titre = _titre(item)
            desc = _description(item)

            # Image : chemin media si disponible
            image_url = ""
            if item.photo:
                image_url = str(item.photo)

            defaults = {
                "titre": titre,
                "description": desc,
                "prix_vente": pv,
                "image_url": image_url,
                "actif": True,
            }

            existing = BoutiqueProduct.objects.filter(stock_item=item).first()
            if existing:
                for k, v in defaults.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
                self.stdout.write(f"  Mis à jour : {titre[:50]} → {pv} €")
            else:
                slug = _slug(titre, item.pk)
                BoutiqueProduct.objects.create(stock_item=item, slug=slug, **defaults)
                created += 1
                self.stdout.write(f"  Créé      : {titre[:50]} → {pv} €")

        self.stdout.write(self.style.SUCCESS(
            f"\nTerminé — {created} créé(s), {updated} mis à jour, {skipped} ignoré(s)."
        ))
