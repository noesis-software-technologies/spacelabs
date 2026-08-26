"""Tâches Celery (exécutées via .apply(), sans broker) et vues ops."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.ops import tasks
from apps.ops.models import MCPAlert, RuntimeHeartbeat, UsageSnapshot
from apps.workspaces.models import HeadlessPane, Pane, PtyPane, Workspace


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="A", cwd="/tmp")


# ── Tâches Celery : le branchement fonctionne (logique testée ailleurs) ─────
@pytest.mark.django_db
def test_snapshot_task_runs(workspace):
    result = tasks.snapshot_usage.apply()
    assert result.successful()
    assert result.result == 1
    assert UsageSnapshot.objects.count() == 1


@pytest.mark.django_db
def test_reap_task_runs(workspace):
    PtyPane.objects.create(workspace=workspace, cmd="sh",
                           status=Pane.Status.RUNNING, runtime_boot_id="x")
    result = tasks.reap_zombies.apply()
    assert result.successful()
    assert result.result == 1  # pas de heartbeat ⇒ tout tombe


@pytest.mark.django_db
def test_scan_mcp_task_runs(workspace, settings):
    settings.COCKPIT_MCP_AUTH_PATTERNS = ["needs authentication"]
    pane = HeadlessPane.objects.create(workspace=workspace)
    pane.events.create(seq=1, origin="raw", event_type="assistant", payload={},
                       normalized={"kind": "assistant", "blocks": [{"type": "text", "text": "needs authentication"}]})
    result = tasks.scan_mcp_auth.apply()
    assert result.successful()
    assert MCPAlert.objects.filter(pane=pane).count() == 1


@pytest.mark.django_db
def test_archive_task_runs(workspace):
    result = tasks.archive_eventlog.apply()
    assert result.successful()
    assert result.result == {"archived": 0, "deleted": 0}


# ── Vues jauges / MCP ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_gauges_requires_login(client):
    assert client.get(reverse("ops:gauges")).status_code == 302


@pytest.mark.django_db
def test_gauges_render(client, user, workspace):
    PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.RUNNING)
    client.force_login(user)
    html = client.get(reverse("ops:gauges")).content.decode()
    # S9 : le vocabulaire du produit est « agent » partout (toolbar, sidebar).
    assert "Agents en cours" in html
    assert "coût du jour" in html
    # La jauge porte son niveau visuel (ok/warn/full) — .ds-gauge-fill[data-level]
    assert "data-level=" in html


@pytest.mark.django_db
def test_gauges_show_mcp_alert_count(client, user, workspace):
    pane = HeadlessPane.objects.create(workspace=workspace)
    MCPAlert.objects.create(pane=pane, detail="x")
    client.force_login(user)
    html = client.get(reverse("ops:gauges")).content.decode()
    assert "alerte" in html and "/mcp" in html


@pytest.mark.django_db
def test_resolve_mcp(client, user, workspace):
    pane = HeadlessPane.objects.create(workspace=workspace)
    alert = MCPAlert.objects.create(pane=pane, detail="x")
    client.force_login(user)
    r = client.post(reverse("ops:resolve_mcp", kwargs={"alert_id": alert.pk}))
    assert r.status_code == 200
    alert.refresh_from_db()
    assert alert.resolved is True


@pytest.mark.django_db
def test_resolve_mcp_isolated_by_owner(client, user, workspace):
    other = get_user_model().objects.create_user(username="bob", password="x")
    ws = Workspace.objects.create(owner=other, name="B", cwd="/tmp")
    pane = HeadlessPane.objects.create(workspace=ws)
    alert = MCPAlert.objects.create(pane=pane, detail="x")
    client.force_login(user)
    r = client.post(reverse("ops:resolve_mcp", kwargs={"alert_id": alert.pk}))
    assert r.status_code == 404
    alert.refresh_from_db()
    assert alert.resolved is False


# ── Réconciliation via commande de management ──────────────────────────────
@pytest.mark.django_db
def test_reconcile_command(workspace):
    from django.core.management import call_command

    PtyPane.objects.create(workspace=workspace, cmd="sh",
                           status=Pane.Status.RUNNING, runtime_boot_id="ancienne-gen")
    call_command("reconcile_panes")
    # BOOT_ID courant != "ancienne-gen" ⇒ le pane est réconcilié
    assert Pane.objects.filter(status=Pane.Status.RUNNING).count() == 0
