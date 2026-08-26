"""Ops chat du consumer, sous ASGI, contre le faux claude."""
from pathlib import Path

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.chat.models import EventLog
from apps.runtime.routing import websocket_urlpatterns
from apps.runtime.services.headless_manager import HeadlessManager
from apps.runtime.services.pane_manager import PaneManager
from apps.workspaces.models import HeadlessPane, Pane, Workspace

FAKE = str(Path(__file__).parent / "support" / "fake_claude.py")

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _fake_claude(settings):
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


async def _make_pane(username="pilote"):
    user = await get_user_model().objects.acreate(username=username)
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    pane = await HeadlessPane.objects.acreate(workspace=ws)
    return user, pane


async def _collect(c, until_kind, budget=80):
    got = []
    for _ in range(budget):
        msg = await c.receive_json_from(timeout=8)
        got.append(msg)
        if msg.get("op") == "chat_event" and msg["event"].get("kind") == until_kind:
            return got
        if msg.get("op") == "error":
            return got
    return got


async def test_chat_send_end_to_end(settings):
    user, pane = await _make_pane()
    c = await _connect(user)

    await c.send_json_to({"op": "chat_attach", "pane_id": pane.pk})
    replay = await c.receive_json_from(timeout=5)
    assert replay["op"] == "chat_replay"
    assert replay["events"] == []
    await c.receive_json_from(timeout=5)  # chat_status

    await c.send_json_to({"op": "chat_send", "pane_id": pane.pk, "text": "salut claude"})
    events = await _collect(c, until_kind="result")
    kinds = [m["event"]["kind"] for m in events if m.get("op") == "chat_event"]
    assert "user" in kinds and "assistant" in kinds and "result" in kinds
    # persistance
    assert await EventLog.objects.filter(pane_id=pane.pk).acount() >= 7

    await c.send_json_to({"op": "chat_kill", "pane_id": pane.pk})
    await c.disconnect()


async def test_attach_replays_persisted_history(settings):
    """F5 : l'historique EventLog est rejoué à l'attache (durable)."""
    user, pane = await _make_pane()
    c1 = await _connect(user)
    await c1.send_json_to({"op": "chat_attach", "pane_id": pane.pk})
    await c1.receive_json_from(timeout=5)  # replay vide
    await c1.receive_json_from(timeout=5)  # status
    await c1.send_json_to({"op": "chat_send", "pane_id": pane.pk, "text": "première tâche"})
    await _collect(c1, until_kind="result")
    await c1.disconnect()

    total = await EventLog.objects.filter(pane_id=pane.pk).acount()
    c2 = await _connect(user)
    await c2.send_json_to({"op": "chat_attach", "pane_id": pane.pk})
    replay = await c2.receive_json_from(timeout=5)
    assert replay["op"] == "chat_replay"
    assert len(replay["events"]) == total   # tout l'historique revient
    assert any("première tâche" in str(e["event"]) for e in replay["events"])
    await c2.disconnect()


async def test_attach_marks_stale_running_dead(settings):
    """Restart serveur simulé : pane running en DB mais pas de session."""
    user, pane = await _make_pane()
    await Pane.objects.filter(pk=pane.pk).aupdate(status=Pane.Status.RUNNING)
    c = await _connect(user)
    await c.send_json_to({"op": "chat_attach", "pane_id": pane.pk})
    await c.receive_json_from(timeout=5)  # replay
    status = await c.receive_json_from(timeout=5)
    assert status == {"op": "chat_status", "pane_id": str(pane.pk), "status": "dead"}
    await pane.arefresh_from_db()
    assert pane.status == Pane.Status.DEAD
    await c.disconnect()


async def test_empty_message_rejected(settings):
    user, pane = await _make_pane()
    c = await _connect(user)
    await c.send_json_to({"op": "chat_send", "pane_id": pane.pk, "text": "   "})
    for _ in range(10):
        msg = await c.receive_json_from(timeout=5)
        if msg["op"] == "error":
            assert "vide" in msg["message"]
            break
    else:
        raise AssertionError("erreur message vide jamais reçue")
    await c.disconnect()


async def test_other_user_cannot_attach_chat(settings):
    user, pane = await _make_pane("alice")
    bob = await get_user_model().objects.acreate(username="bob")
    c = await _connect(bob)
    await c.send_json_to({"op": "chat_attach", "pane_id": pane.pk})
    msg = await c.receive_json_from(timeout=5)
    assert msg["op"] == "error" and "inconnu" in msg["message"]
    await c.disconnect()
