"""HeadlessManager contre le FAUX claude stream-json (subprocess réel).

Vérifie le bout-en-bout : envoi d'un tour → événements Claude parsés →
persistés en EventLog → diffusés ; et le pipeline public/privé (§2.13)
identique au PTY.
"""
import asyncio
from pathlib import Path

import pytest
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model

from apps.chat.models import EventLog
from apps.runtime.services.headless_manager import HeadlessManager
from apps.runtime.services.pane_manager import OBSERVER_GROUP, PaneManager
from apps.workspaces.models import HeadlessPane, Workspace

FAKE = str(Path(__file__).parent / "support" / "fake_claude.py")

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _fake_claude(settings):
    settings.COCKPIT_CLAUDE_BIN = FAKE
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = []  # le faux n'a pas besoin d'args
    HeadlessManager.reset_for_tests()
    PaneManager.reset_for_tests()
    yield
    HeadlessManager.reset_for_tests()
    PaneManager.reset_for_tests()


async def _make_pane(username="pilote", is_public=False):
    user = await get_user_model().objects.acreate(username=username)
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    pane = await HeadlessPane.objects.acreate(workspace=ws)
    return user, pane


async def _wait_events(pane_id, min_count, timeout=8.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        count = await EventLog.objects.filter(pane_id=pane_id).acount()
        if count >= min_count:
            return count
        await asyncio.sleep(0.05)
    return await EventLog.objects.filter(pane_id=pane_id).acount()


async def test_full_exchange_persists_every_event(settings):
    user, pane = await _make_pane()
    manager = HeadlessManager.get()
    await manager.start(str(pane.pk), owner_id=user.pk, cwd="/tmp")
    await manager.send(str(pane.pk), "fais un truc", owner_id=user.pk)

    # 1 user + init + (text, tool_use, tool_result, text, result) = 7 événements
    count = await _wait_events(pane.pk, 7)
    assert count >= 7

    types = [t async for t in EventLog.objects.filter(pane_id=pane.pk)
             .order_by("seq").values_list("event_type", flat=True)]
    assert types[0] == "user"          # le tour humain d'abord
    assert "system" in types           # init
    assert "result" in types           # clôture avec coût/durée
    # séquence strictement croissante et unique
    seqs = [s async for s in EventLog.objects.filter(pane_id=pane.pk)
            .order_by("seq").values_list("seq", flat=True)]
    assert seqs == list(range(1, len(seqs) + 1))

    # le contenu du prompt se retrouve dans un événement normalisé
    norms = [n async for n in EventLog.objects.filter(pane_id=pane.pk)
             .values_list("normalized", flat=True)]
    assert any("fais un truc" in str(n) for n in norms)

    await manager.kill(str(pane.pk), owner_id=user.pk)


async def test_private_chat_never_reaches_observer(settings):
    user, pane = await _make_pane()
    manager = HeadlessManager.get()
    PaneManager.get().live_by_owner[user.pk] = True  # live ON mais pane PRIVÉ

    layer = get_channel_layer()
    channel = await layer.new_channel()
    await layer.group_add(OBSERVER_GROUP, channel)

    await manager.start(str(pane.pk), owner_id=user.pk, cwd="/tmp", is_public=False)
    await manager.send(str(pane.pk), "contenu prive", owner_id=user.pk)
    await _wait_events(pane.pk, 7)

    # Rien sur le groupe observateur
    got = []
    try:
        while True:
            got.append(await asyncio.wait_for(layer.receive(channel), timeout=0.5))
    except asyncio.TimeoutError:
        pass
    assert [m for m in got if m.get("event") == "chat"] == []
    assert manager.replay_events(str(pane.pk)) == []
    await manager.kill(str(pane.pk), owner_id=user.pk)


async def test_public_chat_streams_redacted(settings):
    from apps.observer.redaction import compile_redactor

    user, pane = await _make_pane(is_public=True)
    pane.is_public = True
    await pane.asave()
    manager = HeadlessManager.get()
    PaneManager.get().live_by_owner[user.pk] = True
    redactor = compile_redactor([("MOTSECRET", "•••", False)])

    layer = get_channel_layer()
    channel = await layer.new_channel()
    await layer.group_add(OBSERVER_GROUP, channel)

    await manager.start(str(pane.pk), owner_id=user.pk, cwd="/tmp",
                        is_public=True, redactor=redactor)
    await manager.send(str(pane.pk), "voici MOTSECRET ici", owner_id=user.pk)
    await _wait_events(pane.pk, 7)

    chat_events = []
    try:
        while True:
            msg = await asyncio.wait_for(layer.receive(channel), timeout=0.5)
            if msg.get("event") == "chat":
                chat_events.append(msg["data"])
    except asyncio.TimeoutError:
        pass

    blob = str(chat_events)
    assert "MOTSECRET" not in blob, "le secret est sorti en clair vers l'observateur"
    assert "•••" in blob
    # Le privé (EventLog) garde le vrai contenu (l'opérateur voit tout).
    norms = [n async for n in EventLog.objects.filter(pane_id=pane.pk)
             .values_list("normalized", flat=True)]
    assert any("MOTSECRET" in str(n) for n in norms)
    # Replay public expurgé
    assert "MOTSECRET" not in str(manager.replay_events(str(pane.pk)))
    await manager.kill(str(pane.pk), owner_id=user.pk)


async def test_kill_stops_session_and_marks_pane_dead(settings):
    user, pane = await _make_pane()
    manager = HeadlessManager.get()
    await manager.start(str(pane.pk), owner_id=user.pk, cwd="/tmp")
    proc = manager.sessions[str(pane.pk)].proc
    await manager.kill(str(pane.pk), owner_id=user.pk)
    assert str(pane.pk) not in manager.sessions
    assert proc.returncode is not None
    await pane.arefresh_from_db()
    assert pane.status == "dead"


async def test_owner_isolation(settings):
    user, pane = await _make_pane()
    manager = HeadlessManager.get()
    await manager.start(str(pane.pk), owner_id=user.pk, cwd="/tmp")
    with pytest.raises(Exception):
        manager.set_visibility(str(pane.pk), True, owner_id=user.pk + 999)
    await manager.kill(str(pane.pk), owner_id=user.pk)
