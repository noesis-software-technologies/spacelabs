"""Tâches Celery du Tasker — un battement, pur DB."""
from celery import shared_task

from .models import Mission
from .services import tick


@shared_task(name="tasker.tick_all")
def tick_all() -> int:
    """Fait avancer toutes les missions en cours.

    L'envoi effectif aux agents est fait par le consumer (qui a la boucle
    asyncio et les managers) ; ici on ne fait que la décision, en base.
    """
    planned = 0
    for mission in Mission.objects.filter(status=Mission.Status.RUNNING):
        planned += len(tick(mission))
    return planned
