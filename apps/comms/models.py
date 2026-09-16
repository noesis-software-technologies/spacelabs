from django.db import models

CHANNELS = [
    ("email", "Email"),
    ("telegram", "Telegram"),
    ("whatsapp", "WhatsApp"),
    ("instagram", "Instagram DM"),
    ("sms", "SMS"),
    ("autre", "Autre"),
]
PRIORITES = [("haute", "Haute"), ("normale", "Normale"), ("basse", "Basse")]
STATUTS = [("nouveau", "Nouveau"), ("en_cours", "En cours"),
           ("repondu", "Répondu"), ("archive", "Archivé")]


class Message(models.Model):
    """Message entrant unifié (tous canaux) — l'espace communication névralgique."""
    channel = models.CharField(max_length=20, choices=CHANNELS, default="email")
    ext_id = models.CharField(max_length=500, unique=True)  # Message-ID / id télégram… (dédup)
    expediteur = models.CharField(max_length=300, blank=True)
    sujet = models.CharField(max_length=500, blank=True)
    corps = models.TextField(blank=True)
    recu_le = models.DateTimeField(null=True, blank=True)
    categorie = models.CharField(max_length=40, blank=True)
    priorite = models.CharField(max_length=10, choices=PRIORITES, default="normale")
    needs_reply = models.BooleanField(default=False)
    statut = models.CharField(max_length=12, choices=STATUTS, default="nouveau")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recu_le", "-id"]
        indexes = [models.Index(fields=["channel", "statut"]),
                   models.Index(fields=["priorite"])]

    def __str__(self):
        return f"[{self.channel}] {self.sujet or self.corps[:50]}"
