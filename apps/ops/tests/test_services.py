"""Services d'exploitation (logique pure, sans Celery)."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.chat.models import EventLog
from apps.ops import services
from apps.ops.models import MCPAlert, RuntimeHeartbeat, UsageSnapshot
from apps.workspaces.models import HeadlessPane, Pane, PtyPane, Workspace


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="A", cwd="/tmp")


def _event(pane, seq, etype, normalized, origin="raw", when=None):
    ev = EventLog.objects.create(
        pane=pane, seq=seq, origin=origin, event_type=etype,
        payload={}, normalized=normalized,
    )
    if when is not None:
        EventLog.objects.filter(pk=ev.pk).update(created_at=when)
    return ev


# ── Agrégation d'usage ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_usage_counts_active_panes(user, workspace, settings):
    settings.COCKPIT_MAX_PANES = 12
    PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.RUNNING)
    PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.DEAD)
    data = services.usage_for_owner(user)
    assert data["active_panes"] == 1
    assert data["max_panes"] == 12


@pytest.mark.django_db
def test_usage_cost_is_max_per_pane_summed(user, workspace):
    p1 = HeadlessPane.objects.create(workspace=workspace)
    p2 = HeadlessPane.objects.create(workspace=workspace)
    # p1 : deux result (cumulatif) → on garde le max (0.05)
    _event(p1, 1, "result", {"kind": "result", "cost_usd": 0.02})
    _event(p1, 2, "result", {"kind": "result", "cost_usd": 0.05})
    # p2 : un result 0.03
    _event(p2, 1, "result", {"kind": "result", "cost_usd": 0.03})
    data = services.usage_for_owner(user)
    assert data["cost_usd_today"] == pytest.approx(0.08)


@pytest.mark.django_db
def test_usage_counts_user_turns_today_only(user, workspace):
    pane = HeadlessPane.objects.create(workspace=workspace)
    _event(pane, 1, "user", {"kind": "user", "text": "a"}, origin="user")
    _event(pane, 2, "user", {"kind": "user", "text": "b"}, origin="user")
    # hier — ne doit pas compter
    _event(pane, 3, "user", {"kind": "user", "text": "vieux"}, origin="user",
           when=timezone.now() - timedelta(days=1))
    data = services.usage_for_owner(user)
    assert data["turns_today"] == 2


@pytest.mark.django_db
def test_snapshot_creates_row_per_owner(user, workspace):
    other = get_user_model().objects.create_user(username="autre", password="x")
    Workspace.objects.create(owner=other, name="B", cwd="/tmp")
    created = services.snapshot_all_owners()
    assert created == 2
    assert UsageSnapshot.objects.filter(owner=user).exists()


@pytest.mark.django_db
def test_external_usage_runs_command(user, settings, tmp_path):
    script = tmp_path / "usage.py"
    script.write_text('import json; print(json.dumps({"fenetre": "3 h", "restant": "72%"}))')
    settings.COCKPIT_USAGE_CMD = ["python3", str(script)]
    ext = services.external_usage()
    assert ext == {"fenetre": "3 h", "restant": "72%"}


@pytest.mark.django_db
def test_external_usage_none_when_unset(settings):
    settings.COCKPIT_USAGE_CMD = []
    assert services.external_usage() is None


@pytest.mark.django_db
def test_external_usage_tolerates_failure(settings):
    settings.COCKPIT_USAGE_CMD = ["false"]
    assert services.external_usage() is None


# ── Réconciliation & faucheur ──────────────────────────────────────────────
@pytest.mark.django_db
def test_reconcile_boot_kills_foreign_generations(workspace):
    current = "gen-current"
    alive = PtyPane.objects.create(workspace=workspace, cmd="sh",
                                   status=Pane.Status.RUNNING, runtime_boot_id=current)
    stale = PtyPane.objects.create(workspace=workspace, cmd="sh",
                                   status=Pane.Status.RUNNING, runtime_boot_id="gen-old")
    idle = PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.IDLE)
    n = services.reconcile_boot(current)
    assert n == 1
    stale.refresh_from_db(); alive.refresh_from_db(); idle.refresh_from_db()
    assert stale.status == Pane.Status.DEAD
    assert alive.status == Pane.Status.RUNNING   # génération courante préservée
    assert idle.status == Pane.Status.IDLE


@pytest.mark.django_db
def test_reap_marks_all_dead_when_daphne_absent(workspace, settings):
    settings.COCKPIT_HEARTBEAT_STALE_SECONDS = 90
    PtyPane.objects.create(workspace=workspace, cmd="sh",
                           status=Pane.Status.RUNNING, runtime_boot_id="whatever")
    # aucun heartbeat ⇒ Daphne considéré absent
    assert not RuntimeHeartbeat.objects.exists()
    n = services.reap_zombies()
    assert n == 1
    assert Pane.objects.filter(status=Pane.Status.RUNNING).count() == 0


@pytest.mark.django_db
def test_reap_spares_current_generation_when_daphne_alive(workspace, settings):
    settings.COCKPIT_HEARTBEAT_STALE_SECONDS = 90
    RuntimeHeartbeat.objects.create(boot_id="gen-live", last_seen=timezone.now())
    alive = PtyPane.objects.create(workspace=workspace, cmd="sh",
                                   status=Pane.Status.RUNNING, runtime_boot_id="gen-live")
    zombie = PtyPane.objects.create(workspace=workspace, cmd="sh",
                                    status=Pane.Status.RUNNING, runtime_boot_id="gen-dead")
    n = services.reap_zombies()
    assert n == 1
    alive.refresh_from_db(); zombie.refresh_from_db()
    assert alive.status == Pane.Status.RUNNING
    assert zombie.status == Pane.Status.DEAD


@pytest.mark.django_db
def test_reap_all_dead_when_heartbeat_stale(workspace, settings):
    settings.COCKPIT_HEARTBEAT_STALE_SECONDS = 90
    RuntimeHeartbeat.objects.create(
        boot_id="gen-live", last_seen=timezone.now() - timedelta(seconds=300)
    )
    PtyPane.objects.create(workspace=workspace, cmd="sh",
                           status=Pane.Status.RUNNING, runtime_boot_id="gen-live")
    n = services.reap_zombies()
    assert n == 1  # battement périmé ⇒ Daphne mort ⇒ tout tombe


# ── Détection MCP ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_scan_mcp_creates_alert_on_match(workspace, settings):
    settings.COCKPIT_MCP_AUTH_PATTERNS = ["needs authentication"]
    pane = HeadlessPane.objects.create(workspace=workspace)
    _event(pane, 1, "assistant",
           {"kind": "assistant", "blocks": [{"type": "text", "text": "Server X needs authentication"}]})
    created = services.scan_mcp_auth()
    assert created == 1
    assert MCPAlert.objects.filter(pane=pane, resolved=False).exists()


@pytest.mark.django_db
def test_scan_mcp_dedupes(workspace, settings):
    settings.COCKPIT_MCP_AUTH_PATTERNS = ["run /mcp"]
    pane = HeadlessPane.objects.create(workspace=workspace)
    _event(pane, 1, "assistant", {"kind": "assistant", "blocks": [{"type": "text", "text": "please run /mcp"}]})
    assert services.scan_mcp_auth() == 1
    _event(pane, 2, "assistant", {"kind": "assistant", "blocks": [{"type": "text", "text": "still run /mcp"}]})
    assert services.scan_mcp_auth() == 0  # alerte non résolue déjà présente
    assert MCPAlert.objects.filter(pane=pane).count() == 1


@pytest.mark.django_db
def test_scan_mcp_ignores_clean_output(workspace, settings):
    settings.COCKPIT_MCP_AUTH_PATTERNS = ["needs authentication"]
    pane = HeadlessPane.objects.create(workspace=workspace)
    _event(pane, 1, "assistant", {"kind": "assistant", "blocks": [{"type": "text", "text": "tout va bien"}]})
    assert services.scan_mcp_auth() == 0


# ── Archivage EventLog ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_archive_purges_old_and_keeps_recent(workspace, settings, tmp_path):
    settings.COCKPIT_EVENTLOG_RETENTION_DAYS = 30
    settings.COCKPIT_EVENTLOG_ARCHIVE_DIR = str(tmp_path)
    pane = HeadlessPane.objects.create(workspace=workspace)
    _event(pane, 1, "assistant", {"kind": "assistant"}, when=timezone.now() - timedelta(days=40))
    _event(pane, 2, "assistant", {"kind": "assistant"}, when=timezone.now() - timedelta(days=5))
    result = services.archive_eventlog()
    assert result["deleted"] == 1
    assert result["archived"] == 1
    assert EventLog.objects.filter(pane=pane).count() == 1  # récent conservé
    # fichier d'archive écrit
    files = list(tmp_path.glob("eventlog-*.jsonl.gz"))
    assert len(files) == 1


@pytest.mark.django_db
def test_archive_noop_when_retention_zero(workspace, settings):
    settings.COCKPIT_EVENTLOG_RETENTION_DAYS = 0
    pane = HeadlessPane.objects.create(workspace=workspace)
    _event(pane, 1, "assistant", {"kind": "assistant"}, when=timezone.now() - timedelta(days=999))
    assert services.archive_eventlog() == {"archived": 0, "deleted": 0}
    assert EventLog.objects.filter(pane=pane).count() == 1
