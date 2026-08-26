"""Boucle d'orchestration — c'est ici que la décision devient un envoi.

Découpage (et pourquoi)
-----------------------
``services.tick()`` **décide** : pur DB, synchrone, testable, appelable depuis
Celery. Il ne peut pas envoyer, parce que les managers (`HeadlessManager`)
vivent en mémoire dans le processus Daphne, pas dans le worker.

``run_once()`` **envoie** : il tourne dans le processus qui possède les
managers, appelle ``tick()`` pour chaque mission, puis pousse la consigne à
l'agent via la capacité ``dispatch`` du registre (S9).

Concurrence : plusieurs processus Daphne peuvent exécuter cette boucle en même
temps. Ce n'est pas un problème — ``claim_next`` réserve la tâche en base avec
``select_for_update(skip_locked=True)``, donc un seul processus l'obtient. Le
travail dupliqué se réduit à une requête vide.

Robustesse : un envoi qui échoue (agent mort entre la décision et l'envoi)
libère immédiatement la tâche via ``fail()`` — sinon elle resterait « en cours »
sans que personne ne travaille.
"""
from __future__ import annotations

import asyncio
import logging

from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger("spacelabs.tasker")

_started = False


@sync_to_async
def _plan_all() -> list[tuple[int, int, str, int]]:
    """Décide (en base) et renvoie de quoi envoyer, sans objets ORM traversants.

    On renvoie des valeurs simples — (task_id, pane_pk, consigne, mission_id) —
    plutôt que des instances : l'envoi se fait côté asyncio, où toucher un objet
    ORM paresseux déclencherait une requête synchrone interdite.
    """
    from .models import Mission
    from .services import tick

    out: list[tuple[int, int, str, int]] = []
    for mission in Mission.objects.filter(status=Mission.Status.RUNNING).select_related("workspace"):
        for task, pane in tick(mission):
            out.append((task.pk, pane.pk, task.brief or task.title, mission.pk))
    return out


@sync_to_async
def _load_pane(pane_pk: int):
    from apps.workspaces.models import Pane

    return Pane.objects.select_related("workspace").get(pk=pane_pk)


@sync_to_async
def _release(task_id: int, reason: str) -> None:
    from .models import Task
    from .services import fail

    task = Task.objects.filter(pk=task_id).first()
    if task is not None:
        fail(task, reason=reason)


async def run_once() -> int:
    """Un tour complet : décider puis envoyer. Renvoie le nombre d'envois."""
    from apps.workspaces.models import registry

    sent = 0
    for task_id, pane_pk, brief, mission_id in await _plan_all():
        try:
            pane = await _load_pane(pane_pk)
            entry = registry[pane.kind]
            await entry.dispatch(pane, brief)
            sent += 1
            logger.info("tasker: tâche %s envoyée au pane %s", task_id, pane_pk)
        except Exception as exc:  # noqa: BLE001
            # L'agent a pu mourir entre la réservation et l'envoi : on relâche
            # la tâche tout de suite plutôt que de la laisser bloquée.
            logger.warning("tasker: envoi tâche %s échoué (%s) — libérée", task_id, exc)
            await _release(task_id, "envoi-impossible")
    return sent


async def _loop() -> None:
    interval = max(2, int(getattr(settings, "COCKPIT_TASKER_TICK_SECONDS", 5)))
    logger.info("boucle d'orchestration démarrée (toutes les %ss)", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await run_once()
        except Exception as exc:  # noqa: BLE001 — la boucle ne doit jamais mourir
            logger.warning("tasker: tour d'orchestration échoué : %s", exc)


def start(loop=None) -> bool:
    """Démarre la boucle si une boucle asyncio tourne. Idempotent.

    Appelé depuis le consumer à la première connexion : à ce moment-là on est
    certain d'être dans le processus ASGI, avec une boucle vivante et les
    managers en mémoire. (À l'import de `asgi.py`, il n'y a pas encore de
    boucle — c'est pour ça que le battement du runtime est un thread.)
    """
    global _started
    if _started or not getattr(settings, "COCKPIT_TASKER_AUTORUN", True):
        return False
    try:
        loop = loop or asyncio.get_running_loop()
    except RuntimeError:
        return False
    _started = True
    loop.create_task(_loop())
    return True


def reset_for_tests() -> None:
    global _started
    _started = False
