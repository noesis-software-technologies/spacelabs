"""Signaux Django — intégrité comptable automatique.

Chaque modification d'une SaleOrderLine ou du prix_achat d'un StockItem
déclenche recalculer_totaux() sur la commande parente via on_commit,
sans jamais bloquer la transaction courante.
"""
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.vinted.models import SaleOrderLine, StockItem


@receiver(post_save, sender=SaleOrderLine)
def ligne_saved(sender, instance, **kwargs):
    transaction.on_commit(lambda: instance.order.recalculer_totaux())


@receiver(post_delete, sender=SaleOrderLine)
def ligne_deleted(sender, instance, **kwargs):
    transaction.on_commit(lambda: instance.order.recalculer_totaux())


@receiver(post_save, sender=StockItem)
def stock_item_saved(sender, instance, update_fields=None, **kwargs):
    """Si le prix_achat du StockItem change et qu'une ligne utilise le fallback,
    recalcule la commande parente."""
    if update_fields and "prix_achat" not in update_fields:
        return
    try:
        ligne = instance.ligne  # OneToOne reverse
    except Exception:
        return
    if ligne.prix_achat_unitaire is None:
        transaction.on_commit(lambda: ligne.order.recalculer_totaux())
