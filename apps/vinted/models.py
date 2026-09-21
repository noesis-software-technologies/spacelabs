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
