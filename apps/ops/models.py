"""Modèles d'exploitation (Sprint 5) : usage, heartbeat runtime, alertes MCP.

Tous alimentés/lus depuis la DB — donc partagés entre le processus Daphne
(qui détient les managers en mémoire) et le worker Celery (qui ne les voit
pas). La DB est la seule source de vérité cross-process.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class UsageSnapshot(models.Model):
    """Instantané périodique dérivé de la DB (EventLog + statuts de panes).

    `external` : sortie JSON d'une commande d'usage optionnelle
    (COCKPIT_USAGE_CMD) — ex. fenêtre de quota réelle de l'abonnement.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usage_snapshots"
    )
    taken_at = models.DateTimeField(auto_now_add=True, db_index=True)
    active_panes = models.PositiveIntegerField(default=0)
    max_panes = models.PositiveIntegerField(default=0)
    cost_usd_today = models.FloatField(default=0.0)
    turns_today = models.PositiveIntegerField(default=0)
    external = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-taken_at"]
        verbose_name = "instantané d'usage"

    def __str__(self):
        return f"{self.owner} @ {self.taken_at:%Y-%m-%d %H:%M} — {self.active_panes}/{self.max_panes}"


class RuntimeHeartbeat(models.Model):
    """Battement du processus Daphne vivant. `boot_id` identifie la génération
    (régénéré à chaque démarrage) ; `last_seen` est rafraîchi périodiquement.

    Permet au worker Celery (autre processus) de savoir si Daphne tourne et
    quelle génération est courante — donc quels panes 'running' sont des
    zombies d'une génération morte."""

    boot_id = models.CharField(max_length=32, unique=True)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "battement runtime"

    def __str__(self):
        return f"{self.boot_id[:8]} — {self.last_seen:%H:%M:%S}"

    @classmethod
    def current(cls):
        """Le battement le plus récent, ou None si aucun."""
        return cls.objects.order_by("-last_seen").first()

    @classmethod
    def is_alive(cls, within_seconds: int | None = None) -> bool:
        hb = cls.current()
        if hb is None:
            return False
        window = within_seconds or settings.COCKPIT_HEARTBEAT_STALE_SECONDS
        return (timezone.now() - hb.last_seen) <= timedelta(seconds=window)


class MCPAlert(models.Model):
    """Signal « un serveur MCP a besoin d'être ré-authentifié » détecté dans le
    flux d'un pane chat. Surfacé dans l'UI en bouton /mcp jusqu'à résolution."""

    pane = models.ForeignKey(
        "workspaces.Pane", on_delete=models.CASCADE, related_name="mcp_alerts"
    )
    detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "alerte MCP"

    def __str__(self):
        return f"pane={self.pane_id} MCP {'résolu' if self.resolved else 'à traiter'}"
