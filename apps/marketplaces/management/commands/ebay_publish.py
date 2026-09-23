"""Met une carte en vente sur eBay : prix fixe (vente directe) ou enchères.

Réutilise une carte source Vinted (`--from-vinted <ref>`) ou une MarketListing
déjà créée (`--id`). Sans `--publish`, on prépare la mise en vente (brouillon)
sans appeler l'API ; avec `--publish`, on pousse sur eBay.

Exemples :
  # préparer une vente directe à 39€ depuis une carte Vinted
  python manage.py ebay_publish --from-vinted c3b10d14ce47 --type fixed --prix 39 --etat mint
  # préparer une enchère (départ 1€, réserve 30€, 7 jours)
  python manage.py ebay_publish --from-vinted c3b10d14ce47 --type auction --prix 1 --reserve 30 --duree 7
  # publier réellement (nécessite les clés eBay en .env.local)
  python manage.py ebay_publish --id 12 --publish
"""
from django.core.management.base import BaseCommand, CommandError

from apps.marketplaces.base import MarketplaceConfigError, MarketplaceAPIError
from apps.marketplaces.ebay import EbayClient
from apps.marketplaces.models import MarketListing
from apps.vinted.models import VintedListing


class Command(BaseCommand):
    help = "Prépare / publie une mise en vente eBay (prix fixe ou enchères)."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, help="MarketListing existant.")
        parser.add_argument("--from-vinted", help="ref/id d'une VintedListing source.")
        parser.add_argument("--type", choices=["fixed", "auction"], default=None)
        parser.add_argument("--prix", type=float, help="Prix fixe / mise de départ.")
        parser.add_argument("--reserve", type=float, help="Prix de réserve (enchères).")
        parser.add_argument("--duree", type=int, help="Durée en jours (enchères).")
        parser.add_argument("--etat", default=None)
        parser.add_argument("--publish", action="store_true", help="Pousse sur eBay.")

    def _source(self, key):
        return (VintedListing.objects.filter(ref=key).first()
                or (VintedListing.objects.filter(pk=key).first() if str(key).isdigit() else None))

    def handle(self, *args, **o):
        if o["id"]:
            ml = MarketListing.objects.filter(pk=o["id"], plateforme="ebay").first()
            if not ml:
                raise CommandError(f"MarketListing eBay introuvable : #{o['id']}")
        else:
            if not o["from_vinted"]:
                raise CommandError("Fournis --id ou --from-vinted.")
            src = self._source(o["from_vinted"])
            if not src:
                raise CommandError(f"VintedListing introuvable : {o['from_vinted']}")
            ml = MarketListing.objects.create(
                plateforme="ebay", listing_type=o["type"] or "fixed", source_listing=src,
                titre=src.titre, description=src.description, images=src.images,
                etat=o["etat"] or "mint", prix=o.get("prix"), prix_reserve=o.get("reserve"),
                duree_jours=o.get("duree"), statut="brouillon")
        # champs surchargés si fournis avec --id
        for f, k in (("prix", "prix"), ("prix_reserve", "reserve"),
                     ("duree_jours", "duree"), ("etat", "etat"), ("listing_type", "type")):
            if o.get(k) is not None:
                setattr(ml, f, o[k])
        ml.save()

        self.stdout.write(f"MarketListing #{ml.pk} [{ml.listing_type}] « {ml.resolved_title()[:60]} » "
                          f"prix {ml.prix} €" + (f" / réserve {ml.prix_reserve}" if ml.prix_reserve else ""))
        if not o["publish"]:
            self.stdout.write(self.style.NOTICE("brouillon prêt (ajoute --publish pour pousser sur eBay)"))
            return

        client = EbayClient()
        try:
            res = (client.publish_auction(ml) if ml.listing_type == "auction"
                   else client.publish_fixed(ml))
        except (MarketplaceConfigError, MarketplaceAPIError) as e:
            ml.statut = "erreur"; ml.message = str(e)[:500]; ml.save(update_fields=["statut", "message"])
            raise CommandError(f"Publication eBay échouée : {e}")
        ml.external_id = res.get("external_id", "")
        ml.url = res.get("url", "")
        ml.statut = "publie"; ml.message = ""
        ml.save(update_fields=["external_id", "url", "statut", "message"])
        self.stdout.write(self.style.SUCCESS(f"✓ publié eBay : {ml.url or ml.external_id}"))
