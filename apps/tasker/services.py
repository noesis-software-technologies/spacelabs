"""Dispatcher — fonctions PURES DB, comme apps/ops/services.py.

Pourquoi pur DB : le worker Celery ne voit pas les managers en mémoire (leçon
S5). Toute décision d'orchestration doit donc être prise depuis la base, seule
source vraie cross-process.

Atomicité : ``claim_next`` prend le verrou avec ``select_for_update
(skip_locked=True)``. Deux workers qui tournent en même temps ne peuvent pas
donner la même tâche à deux agents — le second saute la ligne verrouillée au
lieu d'attendre.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.runtime.capacity import running_in_workspace, workspace_limit
from apps.workspaces.models import Pane, registry

from .models import Assignment, Mission, Task

logger = logging.getLogger("spacelabs.tasker")


def refresh_ready(mission: Mission) -> int:
    """Passe en READY les tâches TODO dont toutes les dépendances sont finies.

    C'est la résolution du DAG. Une tâche dont une dépendance a ÉCHOUÉ ne
    devient pas prête : elle passe BLOCKED (sinon on lancerait une tâche dont
    le prérequis n'existe pas).
    """
    changed = 0
    for task in mission.tasks.filter(status=Task.Status.TODO).prefetch_related("depends_on"):
        deps = list(task.depends_on.all())
        if any(d.status == Task.Status.FAILED for d in deps):
            task.status = Task.Status.BLOCKED
            task.save(update_fields=["status"])
            changed += 1
            continue
        if all(d.status == Task.Status.DONE for d in deps):
            task.status = Task.Status.READY
            task.save(update_fields=["status"])
            changed += 1
    return changed


def eligible_panes(mission: Mission):
    """Agents capables de recevoir une tâche automatisée.

    Deux filtres, tous deux structurels :
    - ``can_autocomplete`` (ADR-1) : seul un type qui sait signaler la fin peut
      être orchestré. Le PTY est exclu — flux ANSI opaque.
    - le pane doit tourner : on n'assigne pas à un agent mort.
    """
    panes = Pane.objects.filter(
        workspace=mission.workspace, status=Pane.Status.RUNNING, is_system=False
    ).order_by("order", "id")
    busy = set(
        Assignment.objects.filter(
            ended_at__isnull=True, task__status=Task.Status.RUNNING
        ).values_list("pane_id", flat=True)
    )
    out = []
    for pane in panes:
        entry = registry.get(pane.kind)
        if entry is None or not entry.can_autocomplete:
            continue
        if pane.pk in busy:
            continue
        out.append(pane)
    return out


def free_slots(mission: Mission) -> int:
    """Places disponibles : borné par la mission ET par la capacité du workspace."""
    running = mission.tasks.filter(status=Task.Status.RUNNING).count()
    by_mission = max(0, mission.max_parallel - running)
    ws_free = max(0, workspace_limit(mission.workspace) - running_in_workspace(mission.workspace))
    # La capacité du workspace compte les agents DÉJÀ démarrés : un agent libre
    # qui tourne déjà ne consomme pas de place supplémentaire. On ne borne donc
    # que si aucun agent libre n'existe (cas « il faudrait en démarrer un »).
    return by_mission if eligible_panes(mission) else min(by_mission, ws_free)


@transaction.atomic
def claim_next(mission: Mission, pane: Pane) -> Task | None:
    """Réserve atomiquement la prochaine tâche prête pour cet agent.

    ``skip_locked`` : si un autre worker tient déjà la ligne, on passe à la
    suivante au lieu d'attendre — pas de double assignation, pas de blocage.
    """
    task = (
        Task.objects.select_for_update(skip_locked=True)
        .filter(mission=mission, status=Task.Status.READY)
        .order_by("order", "id")
        .first()
    )
    if task is None:
        return None
    task.status = Task.Status.RUNNING
    task.attempts += 1
    task.save(update_fields=["status", "attempts"])
    Assignment.objects.create(task=task, pane=pane)
    logger.info("tasker: %s → pane %s (essai %d)", task.key, pane.pk, task.attempts)
    return task


def complete(task: Task, cost_usd=0, outcome: str = "done") -> Task:
    """Marque la tâche finie et débloque la suite du DAG."""
    task.status = Task.Status.DONE
    task.cost_usd = (task.cost_usd or 0) + (cost_usd or 0)
    task.save(update_fields=["status", "cost_usd"])
    task.assignments.filter(ended_at__isnull=True).update(
        ended_at=timezone.now(), outcome=outcome
    )
    refresh_ready(task.mission)
    _settle(task.mission)
    return task


def fail(task: Task, reason: str = "error") -> Task:
    """Échec : on retente tant qu'il reste des essais, sinon on gèle la branche.

    ``attempts`` est relu en base : l'appelant tient souvent une instance
    chargée AVANT le claim (le consumer, par exemple), donc son compteur est
    périmé. S'y fier ferait retenter une tâche au-delà de ``max_attempts`` —
    boucle infinie sur une tâche qui échoue systématiquement.
    """
    task.attempts = (
        Task.objects.filter(pk=task.pk).values_list("attempts", flat=True).first()
        or task.attempts
    )
    task.assignments.filter(ended_at__isnull=True).update(
        ended_at=timezone.now(), outcome=reason
    )
    task.status = Task.Status.READY if task.can_retry else Task.Status.FAILED
    task.save(update_fields=["status"])
    if task.status == Task.Status.FAILED:
        refresh_ready(task.mission)   # propage le blocage aux dépendantes
    _settle(task.mission)
    return task


def _settle(mission: Mission) -> None:
    """Clôt la mission quand plus rien ne peut avancer."""
    tasks = list(mission.tasks.all())
    if not tasks:
        return
    if all(t.status == Task.Status.DONE for t in tasks):
        mission.status = Mission.Status.DONE
    elif any(t.status in (Task.Status.FAILED, Task.Status.BLOCKED) for t in tasks) and not any(
        t.status in (Task.Status.READY, Task.Status.RUNNING, Task.Status.TODO) for t in tasks
    ):
        mission.status = Mission.Status.FAILED
    else:
        return
    mission.save(update_fields=["status"])


async def dispatch_task(task: Task, pane: Pane) -> None:
    """Envoie la consigne à l'agent — sans jamais tester son type (§6.9)."""
    entry = registry[pane.kind]
    await entry.dispatch(pane, task.brief or task.title)


def reconcile_boot() -> int:
    """Libère les tâches en vol d'une génération de serveur morte.

    Appelée depuis ``on_server_boot()`` — au redémarrage, aucune session n'a
    survécu : toute tâche RUNNING est orpheline. Jusqu'ici elle était récupérée
    par effet de bord (``reap_stale`` voyait l'agent non-RUNNING au tour
    suivant). C'était correct mais implicite : si un pane restait marqué
    RUNNING en base, la tâche serait restée bloquée indéfiniment.
    """
    freed = 0
    for assignment in (
        Assignment.objects.filter(ended_at__isnull=True, task__status=Task.Status.RUNNING)
        .select_related("task")
    ):
        fail(assignment.task, reason="redemarrage-serveur")
        freed += 1
    if freed:
        logger.info("tasker: %d tâche(s) en vol libérée(s) au boot", freed)
    return freed


def reap_stale(mission: Mission) -> int:
    """Libère les tâches dont l'agent est mort ou qui traînent trop longtemps.

    Deux cas, tous deux détectés en base (donc survivant à un redémarrage) :

    - **agent mort** : le pane n'est plus RUNNING. Sans ça la tâche resterait
      « en cours » pour toujours et occuperait une place de `max_parallel`.
    - **dépassement de durée** : garde-fou contre un agent qui ne répond jamais
      (`COCKPIT_TASKER_TASK_TIMEOUT_SECONDS`).

    Une tâche libérée repasse par ``fail()`` : elle est donc retentée s'il lui
    reste des essais, et gelée sinon — même politique que n'importe quel échec.
    """
    from django.conf import settings

    timeout = int(getattr(settings, "COCKPIT_TASKER_TASK_TIMEOUT_SECONDS", 900))
    deadline = timezone.now() - timezone.timedelta(seconds=timeout)
    freed = 0
    open_assignments = (
        Assignment.objects.filter(
            ended_at__isnull=True, task__mission=mission, task__status=Task.Status.RUNNING
        ).select_related("task", "pane")
    )
    for assignment in open_assignments:
        if assignment.pane.status != Pane.Status.RUNNING:
            fail(assignment.task, reason="agent-mort")
            freed += 1
        elif assignment.started_at < deadline:
            fail(assignment.task, reason="delai-depasse")
            freed += 1
    return freed


def complete_from_result(pane: Pane, normalized: dict) -> Task | None:
    """Clôt la tâche en cours d'un agent à partir d'un événement ``result``.

    C'est le signal de fin de l'ADR-1 : ``stream-json`` émet un ``result`` qui
    porte le coût et le drapeau d'erreur. On ne parse rien d'autre, et surtout
    pas le contenu — juste la fin de tour.
    """
    assignment = (
        Assignment.objects.filter(
            pane=pane, ended_at__isnull=True, task__status=Task.Status.RUNNING
        )
        .select_related("task")
        .order_by("-started_at")
        .first()
    )
    if assignment is None:
        return None          # l'agent travaillait pour un humain, pas pour une mission
    task = assignment.task
    cost = 0
    if isinstance(normalized, dict):
        try:
            cost = float(normalized.get("cost_usd") or 0)
        except (TypeError, ValueError):
            cost = 0
    if isinstance(normalized, dict) and normalized.get("is_error"):
        return fail(task, reason="result-erreur")
    return complete(task, cost_usd=cost)


def tick(mission: Mission) -> list[tuple[Task, Pane]]:
    """Un tour d'orchestration : prépare le DAG, puis assigne ce qui peut l'être.

    Renvoie les couples (tâche, agent) à envoyer. L'envoi lui-même est async et
    reste à la charge de l'appelant : cette fonction est synchrone et pure DB,
    donc appelable depuis Celery comme depuis un test.
    """
    if mission.status != Mission.Status.RUNNING:
        return []
    if mission.over_budget:
        mission.status = Mission.Status.PAUSED
        mission.save(update_fields=["status"])
        logger.warning("tasker: mission %s en pause — budget dépassé", mission.pk)
        return []

    reap_stale(mission)
    refresh_ready(mission)
    planned: list[tuple[Task, Pane]] = []
    slots = free_slots(mission)
    for pane in eligible_panes(mission):
        if slots <= 0:
            break
        task = claim_next(mission, pane)
        if task is None:
            break
        planned.append((task, pane))
        slots -= 1
    return planned
