"""Ops S6 côté consumer : reprise (flag nettoyé, --continue) et attach générique."""
from pathlib import Path

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.runtime.routing import websocket_urlpatterns
from apps.runtime.services.headless_manager import HeadlessManager
from apps.runtime.services.pane_manager import PaneManager
from apps.workspaces.models import HeadlessPane, Pane, Workspace

FAKE = str(Path(__file__).parent.parent.parent / "chat" / "tests" / "support" / "fake_claude.py")

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _fake(settings):
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
    ok, _ = await c.connect()
    assert ok
    return c


async def _pane(resume_pending=False):
    user = await get_user_model().objects.acreate(username="pilote")
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    pane = await HeadlessPane.objects.acreate(workspace=ws, resume_pending=resume_pending)
    return user, pane


async def test_chat_start_resume_clears_flag(settings):
    user, pane = await _pane(resume_pending=True)
    c = await _connect(user)
    await c.send_json_to({"op": "chat_start", "pane_id": pane.pk, "resume": True})
    # attendre le passage running
    for _ in range(10):
        msg = await c.receive_json_from(timeout=5)
        if msg.get("op") == "chat_status" and msg["status"] == "running":
            break
    await pane.arefresh_from_db()
    assert pane.status == Pane.Status.RUNNING
    assert pane.resume_pending is False  # nettoyé par _stamp_running
    await c.send_json_to({"op": "chat_kill", "pane_id": pane.pk})
    await c.disconnect()


async def test_resume_passes_continue_flag(settings, monkeypatch):
    """La reprise doit passer --continue au binaire (best-effort continuation)."""
    user, pane = await _pane(resume_pending=True)
    captured = {}
    real_start = HeadlessManager.start

    async def spy(self, *args, **kwargs):
        captured["resume"] = kwargs.get("resume")
        return await real_start(self, *args, **kwargs)

    monkeypatch.setattr(HeadlessManager, "start", spy)
    c = await _connect(user)
    await c.send_json_to({"op": "chat_start", "pane_id": pane.pk, "resume": True})
    for _ in range(10):
        msg = await c.receive_json_from(timeout=5)
        if msg.get("op") == "chat_status" and msg["status"] == "running":
            break
    assert captured.get("resume") is True
    await c.send_json_to({"op": "chat_kill", "pane_id": pane.pk})
    await c.disconnect()


async def test_generic_attach_dispatches_headless_to_chat_replay(settings):
    """Sur reconnexion, shell.js envoie `attach` pour TOUS les panes ; un pane
    headless doit recevoir son replay chat (et non une erreur PTY)."""
    user, pane = await _pane()
    c = await _connect(user)
    # simuler la ré-attache générique de shell.js
    await c.send_json_to({"op": "attach", "pane_id": pane.pk})
    msg = await c.receive_json_from(timeout=5)
    assert msg["op"] == "chat_replay"   # dispatché vers le chat, pas d'erreur
    assert msg["pane_id"] == str(pane.pk)
    await c.disconnect()
