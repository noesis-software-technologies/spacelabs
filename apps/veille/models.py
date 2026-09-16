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
    blog_cible = models.ForeignKey(
        Blog, null=True, blank=True, on_delete=models.SET_NULL, related_name="items"
    )
    statut = models.CharField(max_length=20, choices=STATUT, default="nouveau")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recu_le", "-id"]

    def __str__(self):
        return f"[{self.categorie}] {self.sujet[:60]}"
