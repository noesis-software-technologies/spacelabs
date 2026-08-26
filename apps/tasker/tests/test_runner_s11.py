"""S11 — la boucle d'exécution : décider → envoyer → détecter la fin.

S10 s'arrêtait à la décision. Ici on prouve que la consigne part vraiment, que
l'événement `result` clôt la tâche, et que rien ne reste bloqué quand un agent
meurt.
"""
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.chat.models import EventLog
from apps.tasker import runner
from apps.tasker.models import Assignment, Mission, Task
from apps.tasker.services import claim_next, complete_from_result, reap_stale, refresh_ready
from apps.workspaces.models import HeadlessPane, Pane, Workspace

FAKE = str(Path(__file__).parents[2] / "chat" / "tests" / "support" / "fake_claude.py")
User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(owner=owner, name="W", cwd="/tmp")


@pytest.fixture
def mission(workspace):
    return Mission.objects.create(
        workspace=workspace, goal="objectif", status=Mission.Status.RUNNING, max_parallel=3
    )


def _task(mission, key="T1", **kw):
    return Task.objects.create(mission=mission, key=key, title=f"tâche {key}", **kw)


def _agent(workspace):
    return HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.RUNNING)


# ── Détection de fin par l'événement `result` (ADR-1) ─────────────────────────
@pytest.mark.django_db
def test_result_event_closes_the_running_task(mission, workspace):
    task = _task(mission)
    refresh_ready(mission)
    pane = _agent(workspace)
    claim_next(mission, pane)

    # Le signal se déclenche à la persistance de l'événement, comme en vrai.
    EventLog.objects.create(
        pane=pane, seq=1, event_type="result",
        payload={}, normalized={"kind": "result", "cost_usd": 0.42},
    )

    task.refresh_from_db()
    assert task.status == Task.Status.DONE
    assert float(task.cost_usd) == 0.42
    assert Assignment.objects.get(task=task).ended_at is not None


@pytest.mark.django_db
def test_result_with_error_fails_the_task(mission, workspace):
    task = _task(mission, max_attempts=1)
    refresh_ready(mission)
    pane = _agent(workspace)
    claim_next(mission, pane)

    EventLog.objects.create(
        pane=pane, seq=1, event_type="result",
        payload={}, normalized={"kind": "result", "is_error": True},
    )

    task.refresh_from_db()
    assert task.status == Task.Status.FAILED


@pytest.mark.django_db
def test_result_from_a_pane_working_for_a_human_is_ignored(mission, workspace):
    """Un agent utilisé à la main émet aussi des `result` : ne rien clôturer."""
    pane = _agent(workspace)
    assert complete_from_result(pane, {"cost_usd": 1}) is None


@pytest.mark.django_db
def test_non_result_events_do_not_close_anything(mission, workspace):
    task = _task(mission)
    refresh_ready(mission)
    pane = _agent(workspace)
    claim_next(mission, pane)

    EventLog.objects.create(pane=pane, seq=1, event_type="assistant",
                            payload={}, normalized={"kind": "text"})
    task.refresh_from_db()
    assert task.status == Task.Status.RUNNING


# ── Récupération : agent mort, tâche qui traîne ───────────────────────────────
@pytest.mark.django_db
def test_dead_agent_frees_its_task(mission, workspace):
    task = _task(mission, max_attempts=2)
    refresh_ready(mission)
    pane = _agent(workspace)
    claim_next(mission, pane)

    pane.status = Pane.Status.DEAD
    pane.save(update_fields=["status"])

    assert reap_stale(mission) == 1
    task.refresh_from_db()
    assert task.status == Task.Status.READY, "il reste un essai → la tâche repart"


@pytest.mark.django_db
def test_task_over_timeout_is_freed(mission, workspace, settings):
    settings.COCKPIT_TASKER_TASK_TIMEOUT_SECONDS = 60
    task = _task(mission, max_attempts=2)
    refresh_ready(mission)
    pane = _agent(workspace)
    claim_next(mission, pane)

    Assignment.objects.filter(task=task).update(
        started_at=timezone.now() - timezone.timedelta(seconds=120)
    )
    assert reap_stale(mission) == 1
    task.refresh_from_db()
    assert task.status == Task.Status.READY


@pytest.mark.django_db
def test_healthy_running_task_is_not_reaped(mission, workspace):
    task = _task(mission)
    refresh_ready(mission)
    claim_next(mission, _agent(workspace))

    assert reap_stale(mission) == 0
    task.refresh_from_db()
    assert task.status == Task.Status.RUNNING


# ── La boucle : décider PUIS envoyer ──────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_run_once_dispatches_to_a_live_agent(settings):
    """Bout en bout : la consigne atteint vraiment la session de l'agent."""
    from apps.runtime.services.headless_manager import HeadlessManager

    settings.COCKPIT_CLAUDE_BIN = FAKE
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = []
    HeadlessManager.reset_for_tests()

    user = await User.objects.acreate(username="p")
    ws = await Workspace.objects.acreate(owner=user, name="W", cwd="/tmp")
    m = await Mission.objects.acreate(workspace=ws, goal="g", status=Mission.Status.RUNNING)
    pane = await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    await Task.objects.acreate(mission=m, key="T1", title="écrire les tests", brief="fais-le")

    headless = HeadlessManager.get()
    await headless.start(str(pane.pk), owner_id=user.pk, cwd="/tmp")
    try:
        sent = await runner.run_once()
        assert sent == 1
        task = await Task.objects.aget(key="T1")
        assert task.status == Task.Status.RUNNING
        assert await Assignment.objects.filter(task=task, pane=pane).aexists()
    finally:
        await headless.shutdown()
        HeadlessManager.reset_for_tests()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_failed_send_releases_the_task():
    """Agent réservé mais session absente : la tâche ne doit pas rester bloquée."""
    from apps.runtime.services.headless_manager import HeadlessManager

    HeadlessManager.reset_for_tests()
    user = await User.objects.acreate(username="p2")
    ws = await Workspace.objects.acreate(owner=user, name="W", cwd="/tmp")
    m = await Mission.objects.acreate(workspace=ws, goal="g", status=Mission.Status.RUNNING)
    await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    await Task.objects.acreate(mission=m, key="T1", title="t", max_attempts=2)

    sent = await runner.run_once()   # aucune session vivante → envoi impossible
    assert sent == 0

    task = await Task.objects.aget(key="T1")
    assert task.status == Task.Status.READY, "la tâche doit être relâchée, pas bloquée"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_run_once_is_a_noop_without_missions():
    assert await runner.run_once() == 0


def test_autorun_disabled_does_not_start(settings):
    settings.COCKPIT_TASKER_AUTORUN = False
    runner.reset_for_tests()
    assert runner.start() is False
