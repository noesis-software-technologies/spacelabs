"""Modèles de la boutique carreaux — mini e-commerce Stripe."""
import uuid
from decimal import Decimal

from django.db import models

from apps.vinted.models import StockItem


class BoutiqueProduct(models.Model):
    """Snapshot du StockItem au moment de la mise en vente en boutique."""

    stock_item = models.OneToOneField(
        StockItem,
        on_delete=models.CASCADE,
        related_name="boutique_product",
        help_text="Article d'entrepôt associé",
    )
    slug = models.SlugField(max_length=200, unique=True)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prix_vente = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        help_text="Prix de vente public (PA × 1.35 recommandé)",
    )
    image_url = models.URLField(
        blank=True,
        help_text="URL Cloudflare Images ou chemin media",
    )
    actif = models.BooleanField(default=True, db_index=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Produit boutique"
        verbose_name_plural = "Produits boutique"

    def __str__(self):
        return f"{self.titre} — {self.prix_vente} €"


def _gen_ref():
    return uuid.uuid4().hex[:20].upper()


class BoutiqueOrder(models.Model):
    """Commande passée via Stripe Checkout."""

    STATUTS = [
        ("pending", "En attente"),
        ("paid", "Payé"),
        ("shipped", "Expédié"),
        ("cancelled", "Annulé"),
    ]

    ref = models.CharField(
        max_length=40, unique=True, default=_gen_ref,
        help_text="Référence courte (uuid4 tronqué)",
    )
    stripe_session_id = models.CharField(max_length=200, blank=True, db_index=True)
    email = models.EmailField()
    nom = models.CharField(max_length=200)
    adresse = models.TextField()
    sous_total = models.DecimalField(
        max_digits=9, decimal_places=2,
        help_text="Somme des produits avant remise",
    )
    remise = models.DecimalField(
        max_digits=9, decimal_places=2, default=Decimal("0.00"),
        help_text="Remise appliquée (10 % si sous-total ≥ 150 €)",
    )
    livraison = models.DecimalField(
        max_digits=9, decimal_places=2, default=Decimal("6.70"),
        help_text="Frais de livraison fixes",
    )
    total = models.DecimalField(
        max_digits=9, decimal_places=2,
        help_text="sous_total - remise + livraison",
    )
    statut = models.CharField(
        max_length=20, choices=STATUTS, default="pending", db_index=True,
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "Commande boutique"
        verbose_name_plural = "Commandes boutique"

    def __str__(self):
        return f"Commande {self.ref} — {self.get_statut_display()} — {self.total} €"


class BoutiqueReview(models.Model):
    """Avis Vinted mis en cache — synchronisés via sync_vinted_reviews."""
    vinted_id = models.CharField(max_length=40, unique=True, help_text="ID Vinted du feedback")
    auteur = models.CharField(max_length=120)
    note = models.PositiveSmallIntegerField(default=5)
    commentaire = models.TextField()
    date = models.DateField(null=True, blank=True)
    vinted_url = models.URLField(blank=True, help_text="Lien profil Vinted du vendeur")
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Avis Vinted"
        verbose_name_plural = "Avis Vinted"

    def __str__(self):
        return f"{self.auteur} — {self.note}★ — {self.commentaire[:40]}"

    @property
    def etoiles(self):
        return "★" * self.note + "☆" * (5 - self.note)


class BoutiqueOrderLine(models.Model):
    """Ligne d'une commande boutique (1 produit, 1 quantité)."""

    order = models.ForeignKey(
        BoutiqueOrder,
        on_delete=models.CASCADE,
        related_name="lignes",
    )
    product = models.ForeignKey(
        BoutiqueProduct,
        on_delete=models.PROTECT,
        related_name="lignes",
    )
    prix_unitaire = models.DecimalField(
        max_digits=9, decimal_places=2,
        help_text="Snapshot du prix au moment de la commande",
    )
    quantite = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]
        verbose_name = "Ligne de commande boutique"
        verbose_name_plural = "Lignes de commande boutique"

    def __str__(self):
        return f"{self.product.titre} × {self.quantite}"

    @property
    def total(self):
        return self.prix_unitaire * self.quantite
