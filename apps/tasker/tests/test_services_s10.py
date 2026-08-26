"""S10 — mécanique d'orchestration du Master Tasker, sans IA.

Si ces tests passent, S11 n'aura qu'à faire écrire le plan par Claude : le
dispatch, le DAG, les reprises et les plafonds sont déjà éprouvés.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.tasker.models import Assignment, Mission, Task
from apps.tasker.services import (
    claim_next,
    complete,
    eligible_panes,
    fail,
    refresh_ready,
    tick,
)
from apps.workspaces.models import HeadlessPane, Pane, PtyPane, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(owner=owner, name="W", cwd="~")


@pytest.fixture
def mission(workspace):
    return Mission.objects.create(
        workspace=workspace, goal="migrer les tests auth",
        status=Mission.Status.RUNNING, max_parallel=3,
    )


def _task(mission, key, **kw):
    return Task.objects.create(mission=mission, key=key, title=f"tâche {key}", **kw)


def _agent(workspace, model=HeadlessPane):
    return model.objects.create(workspace=workspace, status=Pane.Status.RUNNING)


# ── Résolution du DAG ─────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_task_without_dependency_becomes_ready(mission):
    t = _task(mission, "T1")
    assert refresh_ready(mission) == 1
    t.refresh_from_db()
    assert t.status == Task.Status.READY


@pytest.mark.django_db
def test_task_waits_for_its_dependency(mission):
    t1, t2 = _task(mission, "T1"), _task(mission, "T2")
    t2.depends_on.add(t1)

    refresh_ready(mission)
    t2.refresh_from_db()
    assert t2.status == Task.Status.TODO, "T2 ne doit pas partir avant T1"

    complete(t1)
    t2.refresh_from_db()
    assert t2.status == Task.Status.READY


@pytest.mark.django_db
def test_failed_dependency_blocks_instead_of_launching(mission):
    """Une tâche dont le prérequis a échoué ne doit PAS partir : elle bloque."""
    t1 = _task(mission, "T1", max_attempts=1)
    t2 = _task(mission, "T2")
    t2.depends_on.add(t1)

    t1.attempts = 1
    t1.save(update_fields=["attempts"])
    fail(t1)

    t1.refresh_from_db()
    t2.refresh_from_db()
    assert t1.status == Task.Status.FAILED
    assert t2.status == Task.Status.BLOCKED


# ── Assignation atomique ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_claim_marks_running_and_records_assignment(mission, workspace):
    _task(mission, "T1")
    refresh_ready(mission)
    pane = _agent(workspace)

    task = claim_next(mission, pane)
    assert task is not None and task.status == Task.Status.RUNNING
    assert task.attempts == 1
    assert Assignment.objects.filter(task=task, pane=pane, ended_at=None).exists()


@pytest.mark.django_db
def test_a_task_is_never_claimed_twice(mission, workspace):
    """Le cœur du dispatcher : deux agents, une seule tâche prête."""
    _task(mission, "T1")
    refresh_ready(mission)
    a, b = _agent(workspace), _agent(workspace)

    first = claim_next(mission, a)
    second = claim_next(mission, b)

    assert first is not None
    assert second is None, "la même tâche a été donnée deux fois"
    assert Assignment.objects.count() == 1


@pytest.mark.django_db
def test_claim_returns_none_when_nothing_ready(mission, workspace):
    _task(mission, "T1")  # reste TODO : refresh_ready non appelé
    assert claim_next(mission, _agent(workspace)) is None


# ── ADR-1 : seul un agent capable de signaler la fin est orchestrable ─────────
@pytest.mark.django_db
def test_pty_agents_are_never_eligible(mission, workspace):
    """Le PTY n'a pas de signal de fin exploitable (flux ANSI opaque)."""
    PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.RUNNING)
    assert eligible_panes(mission) == []


@pytest.mark.django_db
def test_headless_agents_are_eligible(mission, workspace):
    pane = _agent(workspace)
    assert [p.pk for p in eligible_panes(mission)] == [pane.pk]


@pytest.mark.django_db
def test_dead_agents_are_not_eligible(mission, workspace):
    HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.DEAD)
    assert eligible_panes(mission) == []


@pytest.mark.django_db
def test_busy_agent_is_not_offered_a_second_task(mission, workspace):
    _task(mission, "T1")
    _task(mission, "T2")
    refresh_ready(mission)
    pane = _agent(workspace)

    claim_next(mission, pane)
    assert eligible_panes(mission) == [], "un agent occupé ne doit pas recevoir 2 tâches"


# ── Reprises et clôture ───────────────────────────────────────────────────────
@pytest.mark.django_db
def test_failure_retries_until_attempts_exhausted(mission, workspace):
    t = _task(mission, "T1", max_attempts=2)
    refresh_ready(mission)
    pane = _agent(workspace)

    claim_next(mission, pane)      # essai 1
    fail(t)
    t.refresh_from_db()
    assert t.status == Task.Status.READY, "il reste un essai → on retente"

    claim_next(mission, pane)      # essai 2
    fail(t)
    t.refresh_from_db()
    assert t.status == Task.Status.FAILED


@pytest.mark.django_db
def test_mission_closes_when_all_tasks_done(mission):
    t1, t2 = _task(mission, "T1"), _task(mission, "T2")
    complete(t1)
    mission.refresh_from_db()
    assert mission.status == Mission.Status.RUNNING
    complete(t2)
    mission.refresh_from_db()
    assert mission.status == Mission.Status.DONE


@pytest.mark.django_db
def test_completion_accumulates_cost(mission):
    t = _task(mission, "T1")
    complete(t, cost_usd=0.25)
    t.refresh_from_db()
    assert float(t.cost_usd) == 0.25


# ── Le tour d'orchestration ───────────────────────────────────────────────────
@pytest.mark.django_db
def test_tick_assigns_ready_tasks_to_free_agents(mission, workspace):
    for k in ("T1", "T2", "T3"):
        _task(mission, k)
    _agent(workspace)
    _agent(workspace)

    planned = tick(mission)
    assert len(planned) == 2, "2 agents libres → 2 tâches parties"
    assert mission.tasks.filter(status=Task.Status.RUNNING).count() == 2
    assert mission.tasks.filter(status=Task.Status.READY).count() == 1


@pytest.mark.django_db
def test_tick_respects_max_parallel(mission, workspace):
    mission.max_parallel = 1
    mission.save(update_fields=["max_parallel"])
    _task(mission, "T1")
    _task(mission, "T2")
    _agent(workspace)
    _agent(workspace)

    assert len(tick(mission)) == 1


@pytest.mark.django_db
def test_tick_does_nothing_when_mission_not_running(mission, workspace):
    mission.status = Mission.Status.PAUSED
    mission.save(update_fields=["status"])
    _task(mission, "T1")
    _agent(workspace)
    assert tick(mission) == []


@pytest.mark.django_db
def test_tick_pauses_mission_over_budget(mission, workspace):
    mission.budget_usd = 1
    mission.save(update_fields=["budget_usd"])
    t = _task(mission, "T1")
    complete(t, cost_usd=1.5)      # dépasse le budget
    _task(mission, "T2")
    _agent(workspace)

    assert tick(mission) == []
    mission.refresh_from_db()
    assert mission.status == Mission.Status.PAUSED


@pytest.mark.django_db
def test_tick_without_eligible_agent_assigns_nothing(mission, workspace):
    _task(mission, "T1")
    PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.RUNNING)
    assert tick(mission) == []


# ── Tenancy ───────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_missions_are_scoped_to_their_owner(mission, workspace):
    other = User.objects.create_user(username="autre", password="x")
    assert Mission.objects.for_owner(other).count() == 0
    assert Mission.objects.for_owner(workspace.owner).count() == 1


# ── Régressions trouvées pendant S10 ──────────────────────────────────────────
@pytest.mark.django_db
def test_fail_rereads_attempts_from_db(mission, workspace):
    """`fail()` ne doit pas se fier au compteur de l'instance en mémoire.

    Le consumer tient une Task chargée AVANT le claim : son `attempts` est
    périmé. S'y fier faisait retenter au-delà de max_attempts (boucle infinie
    sur une tâche qui échoue toujours).
    """
    t = _task(mission, "T1", max_attempts=1)
    refresh_ready(mission)
    pane = _agent(workspace)

    stale = Task.objects.get(pk=t.pk)   # attempts = 0
    claim_next(mission, pane)           # en base : attempts = 1
    fail(stale)                         # doit voir 1, pas 0

    stale.refresh_from_db()
    assert stale.status == Task.Status.FAILED


@pytest.mark.django_db
def test_adding_a_task_reopens_a_closed_mission(mission):
    """Le replan de S11 ajoute des tâches après coup : la mission doit repartir."""
    complete(_task(mission, "T1"))
    mission.refresh_from_db()
    assert mission.status == Mission.Status.DONE

    _task(mission, "T2")
    mission.refresh_from_db()
    assert mission.status == Mission.Status.RUNNING
