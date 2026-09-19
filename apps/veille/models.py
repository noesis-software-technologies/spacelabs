from django.db import models

# 9 catégories principales (chacune = une sous-marque / blog de la constellation)
CATEGORIES = [
    ("hotellerie", "Hôtellerie & voyage"),
    ("design", "Design & art de vivre"),
    ("mode", "Mode & lifestyle"),
    ("food", "Gastronomie & boissons"),
    ("culture", "Art, culture & patrimoine"),
    ("habitat", "Architecture & habitat"),
    ("beaute", "Beauté & bien-être"),
    ("societe", "Société & tendances"),
    ("events", "Salons & événements"),
    ("autre", "Autre / à trier"),
]


class Blog(models.Model):
    """Un blog de la constellation. 13-atmosphere.com = principal ; un blog par catégorie."""
    STATUT = [("actif", "Actif"), ("a_ouvrir", "À ouvrir")]
    nom = models.CharField(max_length=120)
    domaine = models.CharField(max_length=200, blank=True)
    categorie = models.CharField(max_length=40, blank=True, help_text="slug de catégorie ; vide = principal")
    is_principal = models.BooleanField(default=False)
    statut = models.CharField(max_length=20, choices=STATUT, default="a_ouvrir")
    # MCP dédié par blog (sinon fallback settings.ATMOSPHERE_MCP_*) — même protocole.
    mcp_url = models.CharField(max_length=300, blank=True, help_text="Endpoint MCP du blog (vide = 13-Atmosphère)")
    mcp_token = models.CharField(max_length=300, blank=True, help_text="Token MCP du blog (secret)")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_principal", "categorie"]

    def __str__(self):
        return f"{self.nom} ({self.domaine or self.categorie or 'principal'})"


class PressItem(models.Model):
    """Un communiqué / dossier de presse reçu (transféré par Thérèse), à dispatcher."""
    STATUT = [
        ("nouveau", "Nouveau"),
        ("assigne", "Assigné"),
        ("redige", "Rédigé"),
        ("publie", "Publié"),
        ("rejete", "Rejeté"),
    ]
    message_id = models.CharField(max_length=500, unique=True)
    expediteur = models.CharField(max_length=200, blank=True)
    sujet = models.CharField(max_length=500)
    recu_le = models.DateTimeField(null=True, blank=True)
    categorie = models.CharField(max_length=40, choices=CATEGORIES, default="autre")
    resume = models.TextField(blank=True)
    corps = models.TextField(blank=True)
    corps_html = models.TextField(blank=True, help_text="Corps HTML brut conservé (ré-extractible)")
    liens_sources = models.JSONField(default=list, blank=True,
                                     help_text="Liens trouvés dans le mail : [{url, texte, kind}]")
    blog_cible = models.ForeignKey(
        Blog, null=True, blank=True, on_delete=models.SET_NULL, related_name="items"
    )
    statut = models.CharField(max_length=20, choices=STATUT, default="nouveau")
    cree_le = models.DateTimeField(auto_now_add=True)

    # ── Pré-rédaction (plume de Thérèse) ──
    DRAFT_STATUT = [
        ("vide", "Pas de brouillon"),
        ("brouillon", "Brouillon généré"),
        ("valide", "Validé"),
        ("publie", "Publié"),
    ]
    draft_titre = models.CharField(max_length=300, blank=True)
    draft_chapo = models.TextField(blank=True)
    draft_corps = models.TextField(blank=True)
    draft_statut = models.CharField(max_length=20, choices=DRAFT_STATUT, default="vide")
    draft_genere_le = models.DateTimeField(null=True, blank=True)
    publier_le = models.DateField(null=True, blank=True, help_text="Date de publication planifiée")

    # ── Visuels (image de référence + carrousel) ──
    image_url = models.URLField(max_length=1000, blank=True, help_text="Image de référence (vignette)")
    images = models.JSONField(default=list, blank=True, help_text="URLs d'images pour le carrousel")
    images_local = models.JSONField(default=list, blank=True,
                                    help_text="Chemins locaux des images téléchargées (pour export MCP)")
    image_alt = models.CharField(max_length=300, blank=True, help_text="Texte alternatif de l'image de référence")

    # ── SEO / méta (prêt pour publication via MCP) ──
    seo_title = models.CharField(max_length=300, blank=True, help_text="Titre optimisé SEO (~60 car.)")
    meta_description = models.CharField(max_length=320, blank=True, help_text="Meta description (~155 car.)")
    slug = models.SlugField(max_length=300, blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="Mots-clés / tags")

    # ── Inter-maillage ──
    liens_internes = models.JSONField(default=list, blank=True,
                                      help_text="Articles liés : [{pk, titre, slug}]")

    # ── Revue éditoriale (panneau de validation) ──
    cover_url = models.CharField(max_length=1000, blank=True,
                                 help_text="Image principale retenue (parmi galerie / proposée)")
    galerie = models.JSONField(default=list, blank=True,
                               help_text="Ordre choisi de la galerie (drag-n-drop) ; 1re = après la cover")

    # ── Publication MCP 13 Atmosphère ──
    mcp_article_id = models.CharField(max_length=64, blank=True,
                                      help_text="article_id renvoyé par le MCP après draft_article")
    mcp_pushed_at = models.DateTimeField(null=True, blank=True, help_text="Dernière poussée vers le MCP")
    MCP_STATUT = [("", "—"), ("draft", "Brouillon sur le blog"), ("published", "Publié (validé)")]
    mcp_status = models.CharField(max_length=20, blank=True, choices=MCP_STATUT,
                                  help_text="État côté blog (rafraîchi via list_drafts)")

    @property
    def toutes_images(self):
        """Toutes les images connues, dédupliquées (locales prioritaires)."""
        seen, out = set(), []
        for u in list(self.images_local or []) + ([self.image_url] if self.image_url else []) \
                + list(self.images or []):
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    @property
    def image_ref(self):
        """Vignette : cover choisie > 1re galerie ordonnée > local > image_url > images."""
        if self.cover_url:
            return self.cover_url
        if self.galerie:
            return self.galerie[0]
        if self.images_local:
            return self.images_local[0]
        return self.image_url or (self.images[0] if self.images else "")

    @property
    def carrousel(self):
        """Ordre d'affichage : cover en tête, puis la galerie ordonnée choisie
        (ou l'ordre par défaut si aucune revue n'a été faite)."""
        base = list(self.galerie) if self.galerie else self.toutes_images
        cover = self.cover_url
        if cover:
            base = [cover] + [u for u in base if u != cover]
        elif cover is None:
            pass
        # garantir unicité + non vide
        seen, out = set(), []
        for u in base:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    class Meta:
        ordering = ["-recu_le", "-id"]

    def __str__(self):
        return f"[{self.categorie}] {self.sujet[:60]}"
