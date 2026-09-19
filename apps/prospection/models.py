from django.conf import settings
from django.db import models
from django.utils import timezone

SOURCES = [("codeur", "Codeur.com"), ("manuel", "Manuel"), ("autre", "Autre")]

# État de l'annonce côté plateforme (porte 1 du process).
ETATS = [
    ("ouvert", "Ouvert"),         # published → on envoie une offre
    ("en_cours", "En cours"),     # in_progress → vivier, pas d'offre
    ("termine", "Terminé"),       # finished → exclu
    ("ferme", "Fermé"),           # closed → exclu
]

# Pipeline de suivi (cahier des charges — 9 statuts).
STATUTS = [
    ("detecte", "Détecté"),
    ("qualifie", "Qualifié"),
    ("offre_envoyee", "Offre envoyée"),
    ("echange", "Échange"),
    ("gagne", "Gagné"),
    ("perdu", "Perdu"),
    ("sans_reponse", "Sans réponse"),
    ("opportunite_future", "Opportunité future"),
    ("rejete", "Rejeté"),
]
STATUTS_ACTIFS = ["detecte", "qualifie", "offre_envoyee", "echange"]

PRIORITES = [("haute", "Haute"), ("normale", "Normale"), ("basse", "Basse")]

MOTIFS_REJET = [
    ("", "—"),
    ("hors_fit", "Hors fit technique"),
    ("budget", "Budget insuffisant"),
    ("trop_offres", "Trop d'offres"),
    ("remontee", "Annonce remontée"),
    ("etat", "État non ouvert"),
    ("brief", "Brief inexploitable"),
    ("doublon", "Doublon"),
]
MOTIFS_PERTE = [
    ("", "—"),
    ("prix", "Prix"),
    ("delai", "Délai"),
    ("concurrent", "Concurrent retenu"),
    ("injoignable", "Client injoignable"),
    ("abandon", "Projet abandonné"),
]


class Opportunity(models.Model):
    """Opportunité de prospection (appel d'offres) suivie selon le cahier des
    charges commercial NOESIS : état plateforme, fraîcheur/concurrence, fit,
    score 0-100, pipeline 9 statuts, motifs de rejet/perte, SLA de réaction."""
    source = models.CharField(max_length=20, choices=SOURCES, default="codeur")
    codeur_id = models.CharField(max_length=32, blank=True, db_index=True,
                                 help_text="guid RSS / id projet — clé de dédup")
    ext_url = models.URLField(max_length=600, unique=True)
    titre = models.CharField(max_length=400)
    budget_texte = models.CharField(max_length=120, blank=True)
    budget_eur = models.PositiveIntegerField(default=0, help_text="Budget estimé en € (parsé)")
    tjm = models.BooleanField(default=False, help_text="Mission en régie (tarif/jour) plutôt que forfait")
    description = models.TextField(blank=True)
    resume_besoin = models.CharField(max_length=400, blank=True, help_text="2 lignes reformulées")
    categorie = models.CharField(max_length=120, blank=True)
    competences = models.JSONField(default=list, blank=True, help_text="Profils recherchés")
    # Fraîcheur / concurrence (horodatés)
    publie_le = models.CharField(max_length=80, blank=True)
    publie_le_dt = models.DateTimeField(null=True, blank=True)
    date_detection = models.DateTimeField(default=timezone.now)
    offres_detection = models.PositiveIntegerField(null=True, blank=True,
                                                   help_text="Nb d'offres relevé à la détection")
    vues = models.CharField(max_length=40, blank=True)
    offres_existantes = models.CharField(max_length=40, blank=True)
    # Client / contact (réservé aux abonnés côté plateforme — contact via messagerie)
    client_nom = models.CharField(max_length=200, blank=True)
    client_societe = models.CharField(max_length=200, blank=True)
    client_localisation = models.CharField(max_length=200, blank=True)
    client_site = models.CharField(max_length=300, blank=True)
    client_url = models.CharField(max_length=600, blank=True)
    contact_tel = models.CharField(max_length=60, blank=True)
    contact_email = models.CharField(max_length=200, blank=True)
    email_verifie = models.BooleanField(default=False)
    # ── CRM ──
    etat = models.CharField(max_length=12, choices=ETATS, default="ouvert")
    stage = models.CharField(max_length=20, choices=STATUTS, default="detecte")  # statut pipeline
    score = models.PositiveIntegerField(default=0, help_text="Score 0-100 (priorisation)")
    priorite = models.CharField(max_length=10, choices=PRIORITES, default="normale")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="opportunites")
    motif_rejet = models.CharField(max_length=16, choices=MOTIFS_REJET, blank=True, default="")
    motif_perte = models.CharField(max_length=16, choices=MOTIFS_PERTE, blank=True, default="")
    date_offre = models.DateField(null=True, blank=True)
    date_relance = models.DateField(null=True, blank=True)
    compte_multi = models.BooleanField(default=False, help_text="Client multi-annonces")
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "-budget_eur", "-id"]
        indexes = [models.Index(fields=["stage"]), models.Index(fields=["etat"]),
                   models.Index(fields=["categorie"]), models.Index(fields=["priorite"])]

    def __str__(self):
        return f"{self.titre[:60]} ({self.budget_eur} €) — {self.get_stage_display()}"

    @property
    def actif(self):
        return self.stage in STATUTS_ACTIFS

    @property
    def delai_detection_h(self):
        if self.publie_le_dt and self.date_detection:
            return round((self.date_detection - self.publie_le_dt).total_seconds() / 3600, 1)
        return None

    @property
    def age_jours(self):
        if self.publie_le_dt:
            return (timezone.now() - self.publie_le_dt).days
        return None


class Activity(models.Model):
    """Historique CRM : changements de statut, notes, offres, relances."""
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="activites")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL)
    texte = models.CharField(max_length=500)
    ancien_stage = models.CharField(max_length=20, blank=True)
    nouveau_stage = models.CharField(max_length=20, blank=True)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return self.texte[:50]
