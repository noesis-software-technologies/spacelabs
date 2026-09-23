from django.db import models

PLATEFORMES = [
    ("ebay", "eBay"),
    ("cardmarket", "CardMarket"),
]

# Type de mise en vente. L'enchère ne concerne qu'eBay ; CardMarket est
# toujours à prix fixe (dépôt de stock sur le catalogue).
TYPES = [
    ("fixed", "Prix fixe (vente directe)"),
    ("auction", "Enchères"),
]

STATUTS = [
    ("brouillon", "Brouillon"),
    ("publie", "Publié"),
    ("erreur", "Erreur"),
    ("vendu", "Vendu"),
    ("cloture", "Clôturé"),
]

# États normalisés (mappés ensuite vers chaque plateforme dans son client).
ETATS = [
    ("mint", "Neuf / Mint"),
    ("near_mint", "Near Mint"),
    ("excellent", "Excellent"),
    ("good", "Bon"),
    ("played", "Joué"),
]


class MarketListing(models.Model):
    """Mise en vente d'une carte sur une place de marché (eBay / CardMarket).

    Réutilise la source carte de `apps.vinted` (titre/description/prix/images/état)
    quand elle existe, ou porte ses propres champs. Ne stocke aucun secret :
    l'authentification passe par les clients (`ebay.py`, `cardmarket.py`) qui
    lisent les clés en variables d'environnement (`.env.local`)."""
    plateforme = models.CharField(max_length=12, choices=PLATEFORMES, db_index=True)
    listing_type = models.CharField(max_length=8, choices=TYPES, default="fixed")

    source_listing = models.ForeignKey(
        "vinted.VintedListing", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="market_listings", help_text="Carte source (annonce Vinted assistée)")
    titre = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    images = models.JSONField(default=list, blank=True)
    etat = models.CharField(max_length=12, choices=ETATS, blank=True)

    # Prix / enchère
    prix = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True,
                               help_text="Prix fixe, ou mise de départ pour une enchère")
    prix_reserve = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True,
                                       help_text="Prix de réserve (enchères eBay)")
    quantite = models.PositiveIntegerField(default=1)
    duree_jours = models.PositiveIntegerField(null=True, blank=True,
                                              help_text="Durée (enchères / GTC eBay)")

    # Référence catalogue (CardMarket : id produit ; eBay : n° annonce/offre)
    external_id = models.CharField(max_length=80, blank=True, db_index=True)
    catalog_id = models.CharField(max_length=80, blank=True,
                                  help_text="ID produit catalogue (CardMarket)")

    statut = models.CharField(max_length=12, choices=STATUTS, default="brouillon", db_index=True)
    url = models.CharField(max_length=500, blank=True)
    message = models.TextField(blank=True, help_text="Dernier message / erreur API")

    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Mise en vente (place de marché)"
        verbose_name_plural = "Mises en vente (places de marché)"

    def __str__(self):
        t = self.titre or (self.source_listing.titre if self.source_listing else self.pk)
        return f"[{self.get_plateforme_display()}/{self.listing_type}] {t}"

    def resolved_title(self):
        return self.titre or (self.source_listing.titre if self.source_listing else "")

    def resolved_description(self):
        return self.description or (self.source_listing.description if self.source_listing else "")

    def resolved_images(self):
        return self.images or (self.source_listing.images if self.source_listing else [])
