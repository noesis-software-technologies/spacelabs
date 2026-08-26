"""S13 — Bridge : vocabulaire vocal déterministe et exécution.

Le vocabulaire est fini et documenté (ADR-4). Ces tests SONT la spécification :
si une phrase courante n'est pas ici, elle n'est pas supportée.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.voice.actions import execute
from apps.voice.intents import MAX_SPAWN, parse
from apps.workspaces.models import HeadlessPane, Pane, Workspace

User = get_user_model()


@pytest.fixture
def workspace(db):
    u = User.objects.create_user(username="pilote", password="x")
    return Workspace.objects.create(owner=u, name="Local", cwd="/tmp")


# ── Vocabulaire ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "said, kind",
    [
        ("où en sont mes agents", "status"),
        ("ou en sont mes agents", "status"),          # transcription sans accent
        ("STATUT", "status"),
        ("qui travaille en ce moment", "status"),
        ("lance deux agents", "spawn"),
        ("ajoute 3 agents", "spawn"),
        ("ouvre un chat", "spawn"),
        ("planifie la mission", "mission_plan"),
        ("découpe la mission", "mission_plan"),
        ("lance la mission", "mission_start"),
        ("mets la mission en pause", "mission_pause"),
        ("ajoute une tâche : relire les tests", "task_add"),
        ("crée une tache pour corriger le lint", "task_add"),
        ("passe en dense", "density"),
        ("mode micro", "density"),
        ("panique", "panic"),
        ("coupe tout", "panic"),
        ("dis à l'agent deux de corriger les tests", "dispatch"),
    ],
)
def test_vocabulary(said, kind):
    assert parse(said).kind == kind


@pytest.mark.parametrize("said", ["", "   ", "bonjour ça va", "raconte-moi une blague"])
def test_unknown_is_refused_not_guessed(said):
    """Mieux vaut « je n'ai pas compris » qu'une action approximative."""
    intent = parse(said)
    assert intent.kind == "unknown"
    assert intent.understood is False


def test_accents_are_normalised():
    assert parse("démarre trois agents").args["count"] == 3
    assert parse("demarre trois agents").args["count"] == 3


def test_spawn_count_is_capped():
    """Une transcription qui dérape ne doit pas ouvrir 40 sessions Claude."""
    assert parse("lance 40 agents").args["count"] == MAX_SPAWN


def test_spawn_defaults_to_one():
    assert parse("ouvre un agent").args["count"] == 1


def test_mission_start_wins_over_spawn():
    """L'ordre des motifs compte : « lance la mission » n'est pas « lance un agent »."""
    assert parse("lance la mission").kind == "mission_start"


def test_task_title_is_extracted():
    assert "relire les tests" in parse("ajoute une tâche : relire les tests").args["title"]


def test_density_level_is_read():
    assert parse("passe en micro").args["level"] == "micro"
    assert parse("mets en compact").args["level"] == "compact"


def test_dispatch_targets_the_right_agent():
    intent = parse("dis à l'agent trois de lancer les tests")
    assert intent.args["pane"] == 3


# ── Exécution ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_status_reports_running_agents(workspace):
    HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.RUNNING)
    HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.IDLE)
    reply = execute(parse("où en sont mes agents"), workspace)
    assert "1 agent" in reply and "2" in reply


@pytest.mark.django_db
def test_status_ignores_system_panes(workspace):
    """Le planificateur n'est pas un agent de travail : il ne se compte pas."""
    HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.RUNNING, is_system=True)
    assert "0 agent" in execute(parse("statut"), workspace)


@pytest.mark.django_db
def test_spawn_creates_agents(workspace):
    execute(parse("lance deux agents"), workspace)
    assert workspace.panes.count() == 2


@pytest.mark.django_db
def test_spawn_stops_at_capacity(workspace, settings):
    """La voix ne contourne pas les plafonds : elle les respecte comme l'UI."""
    settings.COCKPIT_MAX_PANES = 2
    settings.COCKPIT_OWNER_MAX_PANES = 0
    HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.RUNNING)
    HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.RUNNING)

    reply = execute(parse("lance 4 agents"), workspace)
    assert "plafond" in reply.lower()
    assert workspace.panes.count() == 2, "aucun agent en trop ne doit rester en base"


@pytest.mark.django_db
def test_task_add_without_mission_explains(workspace):
    assert "mission" in execute(parse("ajoute une tâche : relire"), workspace).lower()


@pytest.mark.django_db
def test_task_add_lands_on_the_latest_mission(workspace):
    from apps.tasker.models import Mission

    m = Mission.objects.create(workspace=workspace, goal="objectif")
    execute(parse("ajoute une tâche : relire les tests"), workspace)
    assert m.tasks.count() == 1
    assert "relire les tests" in m.tasks.first().title


@pytest.mark.django_db
def test_mission_start_and_pause(workspace):
    from apps.tasker.models import Mission

    m = Mission.objects.create(workspace=workspace, goal="objectif")
    execute(parse("lance la mission"), workspace)
    m.refresh_from_db()
    assert m.status == Mission.Status.RUNNING

    execute(parse("mets la mission en pause"), workspace)
    m.refresh_from_db()
    assert m.status == Mission.Status.PAUSED


@pytest.mark.django_db
def test_panic_cuts_the_live_and_privatises(workspace):
    from apps.observer.models import ObserverSettings

    pane = HeadlessPane.objects.create(workspace=workspace, is_public=True)
    s = ObserverSettings.for_owner(workspace.owner)
    s.live = True
    s.save(update_fields=["live"])

    execute(parse("panique"), workspace)

    pane.refresh_from_db()
    s.refresh_from_db()
    assert pane.is_public is False
    assert s.live is False


@pytest.mark.django_db
def test_unknown_lists_what_bridge_can_do(workspace):
    reply = execute(parse("raconte une blague"), workspace)
    assert "Je sais faire" in reply


# ── Endpoint ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_command_endpoint_routes_and_answers(client, workspace):
    client.force_login(workspace.owner)
    r = client.post("/voice/commande/", {"text": "statut", "workspace": workspace.slug})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "status" and data["understood"] is True


@pytest.mark.django_db
def test_command_endpoint_requires_login(client, workspace):
    r = client.post("/voice/commande/", {"text": "statut", "workspace": workspace.slug})
    assert r.status_code in (302, 403)


@pytest.mark.django_db
def test_command_endpoint_refuses_someone_elses_workspace(client, workspace):
    other = User.objects.create_user(username="autre", password="x")
    client.force_login(other)
    r = client.post("/voice/commande/", {"text": "statut", "workspace": workspace.slug})
    assert r.status_code == 404


# ── Dette réglée : réconciliation explicite au boot ───────────────────────────
@pytest.mark.django_db
def test_boot_reconciliation_frees_in_flight_tasks(workspace):
    """Au redémarrage, aucune session n'a survécu : les tâches en vol sont
    orphelines. Avant, elles étaient récupérées par effet de bord."""
    from apps.tasker.models import Assignment, Mission, Task
    from apps.tasker.services import claim_next, reconcile_boot, refresh_ready

    m = Mission.objects.create(workspace=workspace, goal="g", status=Mission.Status.RUNNING)
    Task.objects.create(mission=m, key="T1", title="t", max_attempts=2)
    refresh_ready(m)
    pane = HeadlessPane.objects.create(workspace=workspace, status=Pane.Status.RUNNING)
    claim_next(m, pane)

    assert reconcile_boot() == 1
    task = m.tasks.get(key="T1")
    assert task.status == Task.Status.READY
    assert Assignment.objects.filter(ended_at__isnull=True).count() == 0
