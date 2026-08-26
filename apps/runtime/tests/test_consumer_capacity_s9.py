"""S9 — le plafond s'applique VRAIMENT sur le socket, pour les deux familles.

Les tests de `test_capacity_s9.py` prouvent la règle ; ceux-ci prouvent qu'elle
est appliquée sur le chemin réel (consumer → manager), et que l'utilisateur
reçoit un message exploitable plutôt qu'une erreur muette.
"""
from pathlib import Path
import logging

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.runtime.routing import websocket_urlpatterns
from apps.runtime.services.headless_manager import HeadlessManager
from apps.runtime.services.pane_manager import PaneManager
from apps.workspaces.models import HeadlessPane, Pane, PtyPane, Workspace

FAKE = str(Path(__file__).parents[2] / "chat" / "tests" / "support" / "fake_claude.py")

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _managers(settings):
    settings.COCKPIT_CLAUDE_BIN = FAKE
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = []
    HeadlessManager.reset_for_tests()
    PaneManager.reset_for_tests()
    yield
    HeadlessManager.reset_for_tests()
    PaneManager.reset_for_tests()


async def _connect(user):
    c = WebsocketCommunicator(URLRouter(websocket_urlpatterns), "/ws/cockpit/")
    c.scope["user"] = user
    connected, _ = await c.connect()
    assert connected
    return c


async def _wait_for(c, op, budget=40):
    """Attend une trame portant cet ``op`` (le flux est asynchrone)."""
    for _ in range(budget):
        msg = await c.receive_json_from(timeout=8)
        if msg.get("op") == op:
            return msg
    raise AssertionError(f"aucune trame {op!r} reçue")


@pytest.mark.asyncio
async def test_headless_start_refused_over_capacity(settings):
    """Le bug n°2 sur le chemin réel : le headless est bien plafonné."""
    settings.COCKPIT_MAX_PANES = 2
    settings.COCKPIT_OWNER_MAX_PANES = 0

    user = await get_user_model().objects.acreate(username="pilote")
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    # Deux agents déjà en cours (en base = source de vérité cross-process).
    await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    third = await HeadlessPane.objects.acreate(workspace=ws)

    c = await _connect(user)
    try:
        await c.send_json_to({"op": "chat_start", "pane_id": third.pk})
        msg = await _wait_for(c, "error")
        assert msg["code"] == "capacity"
        assert "plafond" in msg["message"].lower()
        # Rien n'a démarré : aucune session ouverte pour ce pane.
        assert str(third.pk) not in HeadlessManager.get().sessions
        await third.arefresh_from_db()
        assert third.status == Pane.Status.IDLE
    finally:
        await c.disconnect()


@pytest.mark.asyncio
async def test_pty_spawn_refused_over_capacity(settings):
    settings.COCKPIT_MAX_PANES = 1
    settings.COCKPIT_OWNER_MAX_PANES = 0

    user = await get_user_model().objects.acreate(username="pilote2")
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    pty = await PtyPane.objects.acreate(workspace=ws, cmd="sh", cwd="/tmp")

    c = await _connect(user)
    try:
        await c.send_json_to({"op": "spawn", "pane_id": pty.pk})
        msg = await _wait_for(c, "error")
        assert msg["code"] == "capacity"
        assert str(pty.pk) not in PaneManager.get().panes
    finally:
        await c.disconnect()


@pytest.mark.asyncio
async def test_capacity_refusal_is_logged(settings, caplog):
    """Un refus de capacité laisse une trace serveur (WARNING avec contexte)."""
    settings.COCKPIT_MAX_PANES = 1
    settings.COCKPIT_OWNER_MAX_PANES = 0

    user = await get_user_model().objects.acreate(username="pilote5")
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    pty = await PtyPane.objects.acreate(workspace=ws, cmd="sh", cwd="/tmp")

    c = await _connect(user)
    try:
        with caplog.at_level(logging.WARNING, logger="spacelabs.runtime"):
            await c.send_json_to({"op": "spawn", "pane_id": pty.pk})
            msg = await _wait_for(c, "error")
            assert msg["code"] == "capacity"
        records = [r for r in caplog.records if r.name == "spacelabs.runtime"]
        assert any(
            r.levelno == logging.WARNING
            and str(pty.pk) in r.getMessage()
            and str(user.pk) in r.getMessage()
            for r in records
        )
    finally:
        await c.disconnect()


@pytest.mark.asyncio
async def test_workspace_limit_applies_on_the_socket(settings):
    """« n instances PAR workspace » : un workspace bridé refuse, l'autre non."""
    settings.COCKPIT_MAX_PANES = 16
    settings.COCKPIT_OWNER_MAX_PANES = 0

    user = await get_user_model().objects.acreate(username="pilote3")
    small = await Workspace.objects.acreate(owner=user, name="petit", cwd="/tmp", max_panes=1)
    await HeadlessPane.objects.acreate(workspace=small, status=Pane.Status.RUNNING)
    blocked = await HeadlessPane.objects.acreate(workspace=small)

    c = await _connect(user)
    try:
        await c.send_json_to({"op": "chat_start", "pane_id": blocked.pk})
        msg = await _wait_for(c, "error")
        assert msg["code"] == "capacity"
        assert "workspace" in msg["message"].lower()
    finally:
        await c.disconnect()


@pytest.mark.asyncio
async def test_restart_of_running_session_is_not_blocked(settings):
    """Un F5 sur un chat vivant ne doit pas se heurter au plafond : ce n'est
    pas une nouvelle instance, c'est un ré-attachement."""
    settings.COCKPIT_MAX_PANES = 1
    settings.COCKPIT_OWNER_MAX_PANES = 0

    user = await get_user_model().objects.acreate(username="pilote4")
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    pane = await HeadlessPane.objects.acreate(workspace=ws)

    c = await _connect(user)
    try:
        await c.send_json_to({"op": "chat_start", "pane_id": pane.pk})
        await _wait_for(c, "chat_status")  # démarre (1/1)
        # Preuve qu'une session réelle tourne (sinon le test passerait sur une
        # branche courte sans rien démarrer, et ne prouverait rien).
        assert str(pane.pk) in HeadlessManager.get().sessions

        # Deuxième chat_start sur le MÊME pane : session vivante → pas de refus.
        await c.send_json_to({"op": "chat_start", "pane_id": pane.pk})
        msg = await _wait_for(c, "chat_status")
        assert msg["status"] == "running"
    finally:
        await c.disconnect()
        await HeadlessManager.get().shutdown()
