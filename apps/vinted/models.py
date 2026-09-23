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
    """Commande Vinted vendue : gestion achat/vente/bénéfice + suivi d'envoi.

    Relie (si possible) l'annonce d'origine (`VintedListing`) et centralise le
    prix d'achat (coût d'acquisition de la carte), le prix de vente (net vendeur
    Vinted), les frais vendeur éventuels et le statut d'expédition. Le bénéfice
    est calculé, jamais saisi — source unique de vérité pour le suivi de marge."""
    plateforme = models.CharField(max_length=12, choices=PLATEFORMES, default="vinted",
                                  db_index=True, help_text="Place de marché de la vente")
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

    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_vente", "-id"]
        verbose_name = "Commande Vinted"
        verbose_name_plural = "Commandes Vinted"

    def __str__(self):
        return f"{self.numero or self.titre or self.pk} — {self.get_statut_envoi_display()}"

    @property
    def benefice(self):
        """Bénéfice net = prix de vente - prix d'achat - frais vendeur.

        Coerce en Decimal : les prix peuvent arriver en float (CLI argparse) et
        Decimal - float lève TypeError."""
        from decimal import Decimal
        d = lambda x: Decimal(str(x)) if x is not None else Decimal("0")  # noqa: E731
        return d(self.prix_vente) - d(self.prix_achat) - d(self.frais)

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
    """Article en stock/entrepôt : acheté mais pas encore listé sur Vinted.

    Permet de définir son devenir (vendre à réception, grader chez Collect Aura
    ou CCC en express) et de suivre son état (transit → reçu → gradé/listé →
    vendu). Le coût unitaire alimentera le prix d'achat de la future vente."""
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
