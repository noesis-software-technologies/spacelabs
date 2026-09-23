"""Dépose une carte en stock sur CardMarket (catalogue).

Étape 1 : trouver le produit du catalogue (`--search` → liste les candidats).
Étape 2 : déposer le stock sur l'id produit choisi (`--product <id>`).

Exemples :
  # chercher le produit dans le catalogue
  python manage.py cardmarket_publish --search "Charizard ex 199/165"
  # déposer 1 ex. NM à 39€ sur le produit 12345 (nécessite les clés MKM)
  python manage.py cardmarket_publish --product 12345 --prix 39 --condition near_mint --publish
  # depuis une carte Vinted (utilise son titre pour la recherche)
  python manage.py cardmarket_publish --from-vinted c3b10d14ce47 --prix 39
"""
from django.core.management.base import BaseCommand, CommandError

from apps.marketplaces.base import MarketplaceAPIError, MarketplaceConfigError
from apps.marketplaces.cardmarket import CardmarketClient
from apps.marketplaces.models import MarketListing
from apps.vinted.models import VintedListing


class Command(BaseCommand):
    help = "Recherche catalogue + dépôt de stock CardMarket."

    def add_arguments(self, parser):
        parser.add_argument("--search", help="Texte de recherche catalogue.")
        parser.add_argument("--from-vinted", help="ref/id VintedListing (titre = recherche).")
        parser.add_argument("--product", help="idProduct CardMarket (dépôt de stock).")
        parser.add_argument("--prix", type=float)
        parser.add_argument("--condition", default="near_mint")
        parser.add_argument("--count", type=int, default=1)
        parser.add_argument("--foil", action="store_true")
        parser.add_argument("--language", type=int, help="idLanguage MKM (def. settings).")
        parser.add_argument("--publish", action="store_true", help="Dépose réellement le stock.")

    def handle(self, *args, **o):
        client = CardmarketClient()
        src = None
        if o["from_vinted"]:
            src = (VintedListing.objects.filter(ref=o["from_vinted"]).first()
                   or (VintedListing.objects.filter(pk=o["from_vinted"]).first()
                       if o["from_vinted"].isdigit() else None))
            if not src:
                raise CommandError(f"VintedListing introuvable : {o['from_vinted']}")

        # Recherche catalogue si pas d'id produit fourni
        if not o["product"]:
            query = o["search"] or (src.titre if src else "")
            if not query:
                raise CommandError("Fournis --search, --from-vinted ou --product.")
            try:
                prods = client.find_product(query)
            except (MarketplaceConfigError, MarketplaceAPIError) as e:
                raise CommandError(f"Recherche CardMarket échouée : {e}")
            if not prods:
                self.stdout.write(self.style.WARNING("Aucun produit trouvé."))
                return
            self.stdout.write(f"{len(prods)} produit(s) — choisis un idProduct puis relance avec --product :")
            for p in prods[:15]:
                self.stdout.write(f"  {p.get('idProduct')} — {p.get('enName') or p.get('locName')} "
                                  f"[{(p.get('expansionName') or '')}]")
            return

        # Dépôt de stock
        if o["prix"] is None:
            raise CommandError("--prix requis pour déposer le stock.")
        ml = MarketListing.objects.create(
            plateforme="cardmarket", listing_type="fixed", source_listing=src,
            titre=(src.titre if src else o.get("search") or ""),
            catalog_id=str(o["product"]), etat=o["condition"], prix=o["prix"],
            quantite=o["count"], statut="brouillon")
        if not o["publish"]:
            self.stdout.write(f"MarketListing #{ml.pk} prêt (produit {o['product']}, {o['prix']} €) — "
                              "ajoute --publish pour déposer le stock.")
            return
        try:
            res = client.add_stock(o["product"], o["prix"], condition=o["condition"],
                                   count=o["count"], is_foil=o["foil"],
                                   comments=(src.titre if src else ""),
                                   language_id=o.get("language"))
        except (MarketplaceConfigError, MarketplaceAPIError) as e:
            ml.statut = "erreur"; ml.message = str(e)[:500]; ml.save(update_fields=["statut", "message"])
            raise CommandError(f"Dépôt CardMarket échoué : {e}")
        arts = (res.get("inserted") or [{}])
        art = arts[0].get("idArticle") if isinstance(arts, list) and arts else ""
        ml.external_id = str(art or "")
        ml.statut = "publie"; ml.message = ""
        ml.save(update_fields=["external_id", "statut", "message"])
        self.stdout.write(self.style.SUCCESS(f"✓ stock déposé CardMarket (article {ml.external_id})"))
