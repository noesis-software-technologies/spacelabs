"""Synchronisation inventaire cross-plateforme.

Règles :
- StockItem vendu (depuis Vinted ou boutique) → désactive BoutiqueProduct
- BoutiqueProduct désactivé (vente boutique) → archive VintedListing correspondant
- Idempotent : les deux sens passent par on_commit pour éviter les deadlocks
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.vinted.models import StockItem


@receiver(post_save, sender=StockItem)
def stock_item_vendu(sender, instance, update_fields=None, **kwargs):
    """Quand un StockItem passe vendu → désactive sa fiche boutique + archive Vinted."""
    if update_fields and "statut" not in update_fields:
        return
    if instance.statut not in ("vendu", "vendu_en_cours"):
        return

    def _sync():
        # Désactiver BoutiqueProduct si présent
        try:
            bp = instance.boutique_product
            if bp.actif:
                bp.actif = False
                bp.save(update_fields=["actif", "maj_le"])
        except Exception:
            pass

        # Archiver VintedListing si présent et publié
        try:
            listing = instance.listing  # OneToOne via VintedListing
            if listing and listing.statut not in ("archive", "vendu"):
                listing.statut = "archive"
                listing.save(update_fields=["statut"])
        except Exception:
            pass

    transaction.on_commit(_sync)
