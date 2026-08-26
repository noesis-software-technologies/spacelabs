"""EventLog — persistance intégrale des événements de chat headless.

Chaque événement stream-json (et chaque tour humain) est stocké verbatim,
numéroté par pane, dans l'ordre. C'est la source de vérité rejouée à
l'attache (F5, reconnexion) et l'archive auditée du Sprint 5.
"""
from django.db import models


class EventLog(models.Model):
    pane = models.ForeignKey(
        "workspaces.Pane", on_delete=models.CASCADE, related_name="events"
    )
    seq = models.PositiveIntegerField()
    # 'raw' = événement Claude brut ; 'user' = tour humain synthétisé.
    origin = models.CharField(max_length=10, default="raw")
    event_type = models.CharField(max_length=30)   # system/assistant/user/result…
    payload = models.JSONField()                   # ligne brute (ou event synthétique)
    normalized = models.JSONField(null=True, blank=True)  # forme d'affichage
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pane_id", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["pane", "seq"], name="uniq_event_seq_per_pane"),
        ]
        indexes = [models.Index(fields=["pane", "seq"])]

    def __str__(self):
        return f"pane={self.pane_id} #{self.seq} {self.event_type}"
