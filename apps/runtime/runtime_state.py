"""Identité de la génération Daphne courante + battement de cœur.

BOOT_ID est régénéré à chaque import du module (donc une fois par processus
Daphne). Les panes spawnés par cette génération sont estampillés avec ce
BOOT_ID ; toute génération antérieure encore 'running' en DB est un zombie.
"""
import uuid

BOOT_ID = uuid.uuid4().hex


def touch_heartbeat() -> None:
    """Écrit/rafraîchit le battement de cette génération. Appelé au boot puis
    périodiquement par la boucle du lifespan ASGI."""
    from django.utils import timezone

    from apps.ops.models import RuntimeHeartbeat

    RuntimeHeartbeat.objects.update_or_create(
        boot_id=BOOT_ID, defaults={"last_seen": timezone.now()}
    )
