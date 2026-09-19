from django.conf import settings
from django.db import models
from django.utils import timezone

SOURCES = [("codeur", "Codeur.com"), ("manuel", "Manuel"), ("autre", "Autre")]

# Pipeline commercial : de la détection d'opportunité au gagné/perdu.
STAGES = [
    ("nouveau", "Nouveau"),
    ("qualifie", "Qualifié"),
    ("contacte", "Contacté"),
    ("proposition", "Proposition"),
    ("gagne", "Gagné"),
    ("perdu", "Perdu"),
]
STAGE_OUVERTS = ["nouveau", "qualifie", "contacte", "proposition"]

PRIORITES = [("haute", "Haute"), ("normale", "Normale"), ("basse", "Basse")]


class Opportunity(models.Model):
    """Opportunité de prospection (appel d'offres Codeur.com, etc.) suivie dans un
    pipeline CRM : visibilité + prise de décision pour les équipes commerciales."""
    source = models.CharField(max_length=20, choices=SOURCES, default="codeur")
    ext_url = models.URLField(max_length=600, unique=True)
    titre = models.CharField(max_length=400)
    budget_texte = models.CharField(max_length=120, blank=True)
    budget_eur = models.PositiveIntegerField(default=0, help_text="Budget estimé en € (parsé)")
    description = models.TextField(blank=True)
    categorie = models.CharField(max_length=120, blank=True)
    competences = models.JSONField(default=list, blank=True)
    publie_le = models.CharField(max_length=80, blank=True)
    deadline_jours = models.CharField(max_length=40, blank=True)
    vues = models.CharField(max_length=40, blank=True)
    offres_existantes = models.CharField(max_length=40, blank=True)
    # Client / contact
    client_nom = models.CharField(max_length=200, blank=True)
    client_societe = models.CharField(max_length=200, blank=True)
    client_localisation = models.CharField(max_length=200, blank=True)
    client_site = models.CharField(max_length=300, blank=True)
    client_url = models.CharField(max_length=600, blank=True)
    contact_tel = models.CharField(max_length=60, blank=True)
    contact_email = models.CharField(max_length=200, blank=True)
    email_verifie = models.BooleanField(default=False)
    # ── CRM ──
    stage = models.CharField(max_length=16, choices=STAGES, default="nouveau")
    priorite = models.CharField(max_length=10, choices=PRIORITES, default="normale")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="opportunites")
    notes = models.TextField(blank=True)
    prochaine_action = models.DateField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-budget_eur", "-id"]
        indexes = [models.Index(fields=["stage"]), models.Index(fields=["categorie"]),
                   models.Index(fields=["priorite"])]

    def __str__(self):
        return f"{self.titre[:60]} ({self.budget_eur} €) — {self.get_stage_display()}"

    @property
    def ouvert(self):
        return self.stage in STAGE_OUVERTS


class Activity(models.Model):
    """Trace d'activité commerciale sur une opportunité (historique CRM)."""
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="activites")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL)
    texte = models.CharField(max_length=500)
    ancien_stage = models.CharField(max_length=16, blank=True)
    nouveau_stage = models.CharField(max_length=16, blank=True)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.texte[:50]}"
