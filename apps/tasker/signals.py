"""Détection de fin de tâche — branchée sur EventLog, pas sur le runtime.

Pourquoi un signal plutôt qu'un appel dans ``HeadlessManager`` : le pipeline
runtime ne doit rien savoir de l'orchestration. Le Tasker s'abonne à ce qui est
déjà persisté (invariant : EventLog est la source de vérité durable), et reste
donc découplé — si le Tasker n'est pas installé, rien ne change.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.chat.models import EventLog

from .services import complete_from_result

logger = logging.getLogger("spacelabs.tasker")


@receiver(post_save, sender=EventLog, dispatch_uid="tasker_result_closes_task")
def close_task_on_result(sender, instance: EventLog, created, **kwargs):
    if not created or instance.event_type != "result":
        return
    try:
        task = complete_from_result(instance.pane, instance.normalized or {})
        if task is not None:
            logger.info("tasker: %s clôturée par result (pane %s)", task.key, instance.pane_id)
    except Exception as exc:  # noqa: BLE001 — jamais casser le flux de chat
        logger.warning("tasker: clôture sur result échouée : %s", exc)
