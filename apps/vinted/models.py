from django.db import models

# États Vinted (l'humain préconise l'état — vérif avant publication).
ETATS = [
    ("neuf_etiquette", "Neuf avec étiquette"),
    ("neuf_sans", "Neuf sans étiquette"),
    ("tres_bon", "Très bon état"),
    ("bon", "Bon état"),
    ("satisfaisant", "Satisfaisant"),
]
STATUTS = [
    ("nouveau", "Photos reçues"),
    ("genere", "Titre/description générés"),
    ("pret", "Prêt à publier"),
    ("publie", "Publié sur Vinted"),
]


class VintedListing(models.Model):
    """Annonce Vinted assistée : on envoie N photos, l'outil choisit la plus
    lisible comme référence, en tire titre + description (méthode du compte),
    puis publie sur Vinted (prix / format colis / état fournis par l'humain)."""
    ref = models.CharField(max_length=40, unique=True)
    images = models.JSONField(default=list, blank=True, help_text="Chemins des photos reçues")
    reference_image = models.CharField(max_length=500, blank=True, help_text="Photo la plus lisible")
    # Générés par l'IA (méthode du compte)
    titre = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    # Fournis par l'humain
    prix = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    format_colis = models.CharField(max_length=60, blank=True, help_text="Taille de colis Vinted")
    etat = models.CharField(max_length=20, choices=ETATS, blank=True)
    marque = models.CharField(max_length=120, blank=True)
    categorie = models.CharField(max_length=120, blank=True)
    # Suivi
    statut = models.CharField(max_length=12, choices=STATUTS, default="nouveau")
    vinted_url = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.titre or self.ref} ({self.get_statut_display()})"


# Plateformes de vente (le module démarre sur Vinted, extensible CardMarket/eBay).
PLATEFORMES = [
    ("vinted", "Vinted"),
    ("cardmarket", "CardMarket"),
    ("ebay", "eBay"),
    ("direct", "Vente directe"),
]

# Suivi d'envoi d'une commande vendue (du paiement à la livraison).
STATUTS_ENVOI = [
    ("a_preparer", "À préparer"),
    ("etiquette", "Étiquette éditée"),
    ("expedie", "Expédié"),
    ("livre", "Livré"),
    ("cloture", "Clôturé"),
    ("probleme", "Problème / litige"),
]
# Statuts considérés « à traiter » dans le dashboard des envois.
STATUTS_ENVOI_A_FAIRE = ("a_preparer", "etiquette")

# Transporteurs courants (le champ reste libre : « autre » possible).
TRANSPORTEURS = [
    ("mondial_relay", "Mondial Relay"),
    ("colissimo", "Colissimo"),
    ("chronopost", "Chronopost"),
    ("shop2shop", "Chronopost Shop2Shop"),
    ("relais_colis", "Relais Colis"),
    ("vinted_go", "Vinted Go"),
    ("lettre_suivie", "Lettre suivie (La Poste)"),
    ("ups", "UPS"),
    ("dpd", "DPD"),
    ("gls", "GLS"),
    ("dhl", "DHL"),
    ("autre", "Autre"),
]
# Modèle d'URL de suivi par transporteur ({t} = n° de suivi).
TRACKING_URLS = {
    "mondial_relay": "https://www.mondialrelay.fr/suivi-de-colis/?numeroExpedition={t}",
    "colissimo": "https://www.laposte.fr/outils/suivre-vos-envois?code={t}",
    "lettre_suivie": "https://www.laposte.fr/outils/suivre-vos-envois?code={t}",
    "chronopost": "https://www.chronopost.fr/tracking-no-cms/suivi-page?listeNumerosLT={t}",
    "shop2shop": "https://www.chronopost.fr/tracking-no-cms/suivi-page?listeNumerosLT={t}",
    "relais_colis": "https://www.relaiscolis.com/suivi-de-colis/?numero={t}",
    "ups": "https://www.ups.com/track?tracknum={t}",
    "dpd": "https://www.dpd.fr/trace/{t}",
    "gls": "https://gls-group.com/FR/fr/suivi-colis?match={t}",
    "dhl": "https://www.dhl.com/fr-fr/home/tracking.html?tracking-id={t}",
}


class VintedOrder(models.Model):
    """Commande omnicanal : Vinted, eBay, CardMarket, vente directe, e-commerce.

    La commande est l'en-tête ; le détail article-par-article est dans `lignes`
    (SaleOrderLine). prix_vente / prix_achat restent des champs pour la lecture
    rapide — mis à jour par recalculer_totaux() depuis les lignes."""
    plateforme = models.CharField(max_length=12, choices=PLATEFORMES, default="vinted",
                                  db_index=True, help_text="Place de marché de la vente")
    fournisseur = models.ForeignKey("Fournisseur", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="ventes",
                                    help_text="Source d'approvisionnement de l'article")
    numero = models.CharField(
        max_length=60, blank=True, db_index=True,
        help_text="N° de commande / transaction (identifiant public de la plateforme)")
    listing = models.ForeignKey(
        VintedListing, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="commandes", help_text="Annonce d'origine (si connue)")
    titre = models.CharField(max_length=200, blank=True,
                             help_text="Libellé de l'article (repli si l'annonce manque)")
    acheteur = models.CharField(max_length=120, blank=True,
                                help_text="Pseudo acheteur Vinted (pas de donnée perso)")

    # Argent (Decimal : pas de flottant sur de la monnaie)
    prix_achat = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True,
                                     help_text="Coût d'acquisition de la carte")
    prix_vente = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True,
                                     help_text="Prix de vente (net vendeur Vinted)")
    frais = models.DecimalField(max_digits=9, decimal_places=2, default=0,
                                help_text="Frais vendeur (port à charge, mise en avant, gradation…)")
    remise = models.DecimalField(max_digits=9, decimal_places=2, default=0,
                                 help_text="Remise accordée à l'acheteur (lot/bundle — déduite du prix nominal)")

    # Envoi
    statut_envoi = models.CharField(max_length=12, choices=STATUTS_ENVOI, default="a_preparer",
                                    db_index=True)
    transporteur = models.CharField(max_length=60, blank=True, choices=TRANSPORTEURS,
                                    help_text="Mondial Relay, Colissimo, Chronopost…")
    tracking = models.CharField(max_length=80, blank=True,
                                help_text="N° de suivi / ticket de référence")

    date_vente = models.DateField(null=True, blank=True)
    date_expedition = models.DateField(null=True, blank=True)
    date_livraison = models.DateField(null=True, blank=True)

    # Lien vers le(s) article(s) d'entrepôt correspondants (M2M : un lot peut
    # regrouper plusieurs StockItems ; un StockItem peut n'apparaître que dans
    # une seule commande active).
    stock_items = models.ManyToManyField(
        "StockItem", blank=True, related_name="commandes",
        help_text="Article(s) d'entrepôt vendus dans cette commande")

    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_vente", "-id"]
        verbose_name = "Commande Vinted"
        verbose_name_plural = "Commandes Vinted"

    def __str__(self):
        return f"{self.numero or self.titre or self.pk} — {self.get_statut_envoi_display()}"

    def recalculer_totaux(self):
        """Recompute prix_vente / prix_achat depuis les SaleOrderLines."""
        from decimal import Decimal
        lignes = list(self.lignes.all())
        if not lignes:
            return
        self.prix_vente = sum((l.total_vente for l in lignes), Decimal("0"))
        if all(l.prix_achat_unitaire is not None for l in lignes):
            self.prix_achat = sum((l.total_achat for l in lignes), Decimal("0"))
        self.save(update_fields=["prix_vente", "prix_achat", "maj_le"])

    @property
    def benefice(self):
        """Bénéfice net.

        Si des lignes existent : sum(benefice_ligne) - remise - frais.
        Sinon fallback sur les champs agrégés (commandes sans lignes)."""
        from decimal import Decimal
        d = lambda x: Decimal(str(x)) if x is not None else Decimal("0")  # noqa: E731
        lignes = self.lignes.all()
        if lignes.exists():
            return sum((l.benefice_ligne for l in lignes), Decimal("0")) - d(self.remise) - d(self.frais)
        return d(self.prix_vente) - d(self.prix_achat) - d(self.frais) - d(self.remise)

    @property
    def prix_nominal(self):
        """Prix avant remise = prix_vente + remise."""
        from decimal import Decimal
        d = lambda x: Decimal(str(x)) if x is not None else Decimal("0")  # noqa: E731
        return d(self.prix_vente) + d(self.remise)

    @property
    def remise_pct(self):
        """Remise en % du prix nominal (None si pas de remise ou prix inconnu)."""
        if not self.remise or not self.prix_vente:
            return None
        return round(float(self.remise) / float(self.prix_nominal) * 100, 1)

    @property
    def marge_pct(self):
        """Marge en % du coût d'acquisition (None si prix d'achat inconnu/0)."""
        if not self.prix_achat:
            return None
        return round(float(self.benefice) / float(self.prix_achat) * 100, 1)

    @property
    def envoi_a_faire(self):
        return self.statut_envoi in STATUTS_ENVOI_A_FAIRE

    @property
    def tracking_url(self):
        """Lien de suivi cliquable (selon transporteur + n° de suivi), sinon ''."""
        tmpl = TRACKING_URLS.get(self.transporteur)
        return tmpl.format(t=self.tracking.strip()) if tmpl and self.tracking else ""

    @property
    def transporteur_label(self):
        return dict(TRANSPORTEURS).get(self.transporteur, self.transporteur or "")


class Fournisseur(models.Model):
    """Fournisseur / source d'approvisionnement (ex. litsou, import_pokepoke)."""
    nom = models.CharField(max_length=120, unique=True)
    canal = models.CharField(max_length=60, blank=True,
                             help_text="Vinted, TikTok, live, site… (où on achète)")
    contact = models.CharField(max_length=200, blank=True, help_text="Pseudo, URL, contact")
    notes = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.nom


# ── Entrepôt : achats/références pas encore listés sur Vinted ──
STOCK_SOURCES = [
    ("tiktok", "TikTok"),
    ("import_pokepoke", "Vinted — import_pokepoke"),
    ("live", "Live"),
    ("vinted", "Vinted"),
    ("autre", "Autre"),
]
# Devenir de l'article une fois reçu.
STOCK_DESTINS = [
    ("a_definir", "À définir"),
    ("vente_directe", "Vendre à réception"),
    ("grade_collectaura", "Grader — Collect Aura (Boulogne-Billancourt, express)"),
    ("grade_ccc", "Grader — CCC (Malakoff, express)"),
    ("garder", "Garder / collection"),
]
STOCK_STATUTS = [
    ("en_transit", "En transit"),
    ("recu", "Reçu"),
    ("a_grader", "À grader"),
    ("en_gradation", "En gradation"),
    ("grade", "Gradé"),
    ("a_lister", "À lister"),
    ("liste", "Listé sur Vinted"),
    ("vendu", "Vendu"),
]


class StockItem(models.Model):
    """Article physique : de l'achat jusqu'à la vente.

    Entité canonique du cycle de vie d'un produit :
      achat → [transit] → reçu → [gradation] → listé → vendu.

    Quand il est publié sur Vinted, `listing` pointe vers la VintedListing
    correspondante (source de la fiche commerciale : titre, photos, URL).
    Quand il est vendu, il apparaît dans `commandes` via la M2M de VintedOrder.
    Le champ `statut` reste la vérité terrain ; `pipeline_statut` enrichit la
    lecture avec l'état de la commande liée."""
    nom = models.CharField(max_length=200)
    reference = models.CharField(max_length=120, blank=True, help_text="N°/set/ref carte")
    fournisseur = models.ForeignKey(Fournisseur, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="articles")
    source = models.CharField(max_length=20, choices=STOCK_SOURCES, default="autre",
                              help_text="Canal d'achat")
    prix_achat = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True,
                                     help_text="Coût unitaire d'acquisition")
    quantite = models.PositiveIntegerField(default=1)
    destin = models.CharField(max_length=20, choices=STOCK_DESTINS, default="a_definir",
                              help_text="Devenir prévu à réception")
    statut = models.CharField(max_length=14, choices=STOCK_STATUTS, default="en_transit",
                              db_index=True)
    gradeur = models.CharField(max_length=120, blank=True,
                               help_text="Ex. Collect Aura (BB) / CCC (Malakoff)")
    # Lien vers la fiche commerciale Vinted (rempli quand l'article est listé).
    listing = models.OneToOneField(
        "VintedListing", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="stock_item",
        help_text="Annonce Vinted associée à cet article (remplie à la publication)")
    photo = models.URLField(blank=True, help_text="URL thumbnail de la carte (Pokellector, scan perso…)")
    date_achat = models.DateField(null=True, blank=True)
    date_reception = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Article en stock (entrepôt)"
        verbose_name_plural = "Entrepôt (stock)"

    def __str__(self):
        return f"{self.nom} ({self.get_statut_display()})"

    @property
    def cout_total(self):
        from decimal import Decimal
        pa = Decimal(str(self.prix_achat)) if self.prix_achat is not None else Decimal("0")
        return pa * self.quantite

    def _get_ligne(self):
        """Retourne la SaleOrderLine liée (OneToOne), ou None."""
        try:
            return self.ligne
        except Exception:
            return None

    @property
    def commande_active(self):
        """VintedOrder liée via SaleOrderLine (ou M2M en fallback)."""
        ligne = self._get_ligne()
        if ligne:
            return ligne.order
        return self.commandes.first()

    @property
    def vinted_url(self):
        """URL de l'annonce Vinted (via listing lié), sinon ''."""
        return self.listing.vinted_url if self.listing else ""

    @property
    def pipeline_statut(self):
        """Lecture unifiée du cycle de vie :
        entrepôt → listé → [statut commande] → vendu."""
        commande = self.commande_active
        if commande:
            return commande.get_statut_envoi_display()
        if self.listing:
            return f"Listé ({self.listing.get_statut_display()})"
        return self.get_statut_display()

    @property
    def est_en_entrepot(self):
        """True si l'article est toujours en entrepôt (non listé, non vendu)."""
        if self._get_ligne():
            return False
        return not self.listing and not self.commandes.exists()

    @property
    def est_vendu(self):
        """True si lié à une commande expédiée/livrée/clôturée, ou statut=vendu."""
        if self.statut == "vendu":
            return True
        ligne = self._get_ligne()
        if ligne:
            return ligne.order.statut_envoi in ("expedie", "livre", "cloture")
        return self.commandes.filter(statut_envoi__in=("expedie", "livre", "cloture")).exists()

    def lier_commande(self, order, prix_vente=None, prix_achat=None):
        """Lie cet article à une commande via SaleOrderLine + passe statut=vendu."""
        SaleOrderLine.objects.update_or_create(
            stock_item=self,
            defaults=dict(
                order=order,
                designation=self.nom,
                prix_vente_unitaire=prix_vente,
                prix_achat_unitaire=prix_achat if prix_achat is not None else self.prix_achat,
            ),
        )
        order.stock_items.add(self)
        self.statut = "vendu"
        self.save(update_fields=["statut", "maj_le"])


class SaleOrderLine(models.Model):
    """Ligne de commande omnicanal : un article vendu, son prix unitaire, son coût.

    Chaque ligne = 1 StockItem physique (ou une référence libre) avec son prix
    de vente et d'achat unitaires. La commande mère (VintedOrder) agrège les
    lignes pour le CA / bénéfice total via recalculer_totaux()."""

    order = models.ForeignKey(
        VintedOrder, on_delete=models.CASCADE, related_name="lignes",
        help_text="Commande parente")
    stock_item = models.OneToOneField(
        StockItem, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="ligne",
        help_text="Article physique correspondant (optionnel pour lignes libres)")
    designation = models.CharField(
        max_length=200, blank=True,
        help_text="Libellé affiché (auto depuis stock_item.nom à la création)")
    prix_vente_unitaire = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Prix de vente par unité (avant remise globale du lot)")
    prix_achat_unitaire = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Coût d'acquisition par unité")
    quantite = models.PositiveIntegerField(default=1)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    def __str__(self):
        label = self.designation or (self.stock_item.nom if self.stock_item else f"Ligne {self.pk}")
        return f"{label} × {self.quantite}"

    def save(self, *args, **kwargs):
        if not self.designation and self.stock_item_id:
            try:
                self.designation = StockItem.objects.get(pk=self.stock_item_id).nom
            except StockItem.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    @property
    def total_vente(self):
        from decimal import Decimal
        d = lambda x: Decimal(str(x)) if x is not None else Decimal("0")  # noqa: E731
        return d(self.prix_vente_unitaire) * self.quantite

    @property
    def total_achat(self):
        from decimal import Decimal
        d = lambda x: Decimal(str(x)) if x is not None else Decimal("0")  # noqa: E731
        return d(self.prix_achat_unitaire) * self.quantite

    @property
    def benefice_ligne(self):
        from decimal import Decimal
        d = lambda x: Decimal(str(x)) if x is not None else Decimal("0")  # noqa: E731
        return (d(self.prix_vente_unitaire) - d(self.prix_achat_unitaire)) * self.quantite
