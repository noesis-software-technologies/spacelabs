"""Consumer S2 — protocole par pane persistant, sous ASGI (Blueprint §2.11)."""
import base64

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.runtime.routing import websocket_urlpatterns
from apps.runtime.services.pane_manager import PaneManager
from apps.workspaces.models import Pane, PtyPane, Workspace

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _fresh_manager():
    PaneManager.reset_for_tests()
    yield
    PaneManager.reset_for_tests()


@pytest.fixture
def app():
    return URLRouter(websocket_urlpatterns)


async def _connect(app, user):
    communicator = WebsocketCommunicator(app, "/ws/cockpit/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    return communicator


async def _make_user(username="pilote"):
    return await get_user_model().objects.acreate(username=username)


async def _make_pane(user, ws_name="Alpha", cmd="sh"):
    workspace = await Workspace.objects.acreate(owner=user, name=ws_name, cwd="/tmp")
    return await PtyPane.objects.acreate(workspace=workspace, cmd=cmd)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


async def _wait_for_output(communicator, pane_id, contains: str, tries=80):
    """Attend une sortie du pane demandé — et vérifie au passage qu'aucune
    trame stdout ne porte un autre pane_id que ceux attendus par ce socket."""
    for _ in range(tries):
        msg = await communicator.receive_json_from(timeout=5)
        if msg["op"] != "stdout":
            continue
        if msg["pane_id"] == str(pane_id) and contains in base64.b64decode(msg["data"]).decode(errors="replace"):
            return msg
    raise AssertionError(f"Sortie attendue jamais reçue : {contains!r}")


async def test_anonymous_is_rejected(app):
    from django.contrib.auth.models import AnonymousUser

    communicator = WebsocketCommunicator(app, "/ws/cockpit/")
    communicator.scope["user"] = AnonymousUser()
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4401


async def test_spawn_by_record_and_roundtrip(app, settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await _make_user()
    record = await _make_pane(user)
    c = await _connect(app, user)

    await c.send_json_to({"op": "spawn", "pane_id": record.pk})
    status = await c.receive_json_from(timeout=5)
    assert status == {"op": "status", "pane_id": str(record.pk), "status": "running"}
    await record.arefresh_from_db()
    assert record.status == Pane.Status.RUNNING

    await c.send_json_to({"op": "stdin", "pane_id": record.pk, "data": _b64("echo DB_$((40+2))\n")})
    await _wait_for_output(c, record.pk, "DB_42")

    await c.send_json_to({"op": "kill", "pane_id": record.pk})
    for _ in range(20):
        msg = await c.receive_json_from(timeout=5)
        if msg.get("op") == "status" and msg.get("status") == "dead":
            break
    await record.arefresh_from_db()
    assert record.status == Pane.Status.DEAD
    await c.disconnect()


async def test_two_workspaces_three_panes_no_stream_mixing(app, settings):
    """Acceptation S2 : 2 workspaces × panes en parallèle, flux jamais mélangés."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    settings.COCKPIT_MAX_PANES = 6
    user = await _make_user()
    ws_a = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    ws_b = await Workspace.objects.acreate(owner=user, name="B", cwd="/tmp")
    panes = []
    for ws in (ws_a, ws_a, ws_b):
        panes.append(await PtyPane.objects.acreate(workspace=ws, cmd="sh"))

    c = await _connect(app, user)
    for p in panes:
        await c.send_json_to({"op": "spawn", "pane_id": p.pk})

    # Un marqueur distinct par pane, envoyés entrelacés.
    for i, p in enumerate(panes):
        await c.send_json_to(
            {"op": "stdin", "pane_id": p.pk, "data": _b64(f"echo MARQUEUR_{i}_$((10+{i}))\n")}
        )

    # Chaque marqueur doit revenir SUR le pane_id qui l'a émis.
    seen = {}
    for _ in range(200):
        msg = await c.receive_json_from(timeout=5)
        if msg["op"] != "stdout":
            continue
        text = base64.b64decode(msg["data"]).decode(errors="replace")
        for i in range(3):
            if f"MARQUEUR_{i}_{10 + i}" in text:
                seen.setdefault(i, msg["pane_id"])
        if len(seen) == 3:
            break
    assert seen == {i: str(panes[i].pk) for i in range(3)}

    for p in panes:
        await c.send_json_to({"op": "kill", "pane_id": p.pk})
    await c.disconnect()


async def test_attach_marks_stale_running_as_dead(app, settings):
    """Restart serveur simulé : DB dit running, runtime vide ⇒ dead + resync."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await _make_user()
    record = await _make_pane(user)
    await Pane.objects.filter(pk=record.pk).aupdate(status=Pane.Status.RUNNING)

    c = await _connect(app, user)
    await c.send_json_to({"op": "attach", "pane_id": record.pk})
    msg = await c.receive_json_from(timeout=5)
    assert msg == {"op": "status", "pane_id": str(record.pk), "status": "dead"}
    await record.arefresh_from_db()
    assert record.status == Pane.Status.DEAD
    await c.disconnect()


async def test_spawn_when_already_running_attaches_instead(app, settings):
    """F5 : un spawn sur un pane déjà vivant rejoue l'historique au lieu de
    doubler le process."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await _make_user()
    record = await _make_pane(user)
    c1 = await _connect(app, user)
    await c1.send_json_to({"op": "spawn", "pane_id": record.pk})
    await c1.receive_json_from(timeout=5)
    await c1.send_json_to({"op": "stdin", "pane_id": record.pk, "data": _b64("echo AVANT_F5\n")})
    await _wait_for_output(c1, record.pk, "AVANT_F5")

    manager = PaneManager.get()
    pid_before = manager.panes[str(record.pk)].proc.pid

    c2 = await _connect(app, user)  # le F5
    await c2.send_json_to({"op": "spawn", "pane_id": record.pk})
    await _wait_for_output(c2, record.pk, "AVANT_F5")  # replay, pas un nouveau shell
    assert manager.panes[str(record.pk)].proc.pid == pid_before

    await c2.send_json_to({"op": "kill", "pane_id": record.pk})
    await c1.disconnect()
    await c2.disconnect()


async def test_other_user_cannot_spawn_or_attach(app, settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    alice = await _make_user("alice")
    bob = await _make_user("bob")
    record = await _make_pane(alice)

    c = await _connect(app, bob)
    for op in ("spawn", "attach"):
        await c.send_json_to({"op": op, "pane_id": record.pk})
        msg = await c.receive_json_from(timeout=5)
        assert msg["op"] == "error"
        assert "inconnu" in msg["message"]
    await c.disconnect()


async def test_invalid_stdin_is_rejected(app, settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await _make_user()
    record = await _make_pane(user)
    c = await _connect(app, user)
    await c.send_json_to({"op": "spawn", "pane_id": record.pk})
    await c.receive_json_from(timeout=5)

    await c.send_json_to({"op": "stdin", "pane_id": record.pk, "data": "%%%pas-du-b64%%%"})
    for _ in range(20):
        msg = await c.receive_json_from(timeout=5)
        if msg["op"] == "error":
            assert "base64" in msg["message"]
            break
    else:
        raise AssertionError("Erreur base64 jamais reçue")

    await c.send_json_to({"op": "kill", "pane_id": record.pk})
    await c.disconnect()
