"""Pipeline public du PaneManager — LE contrat de confidentialité S3.

Chaque test formule une propriété que l'observateur ne doit jamais pouvoir
violer : pas de flux privé, pas de passé révélé, pas de secret en clair.
"""
import asyncio
import base64

import pytest
from channels.layers import get_channel_layer

from apps.observer.redaction import compile_redactor
from apps.runtime.services.pane_manager import OBSERVER_GROUP, PaneManager

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fresh_manager():
    PaneManager.reset_for_tests()
    yield
    PaneManager.reset_for_tests()


async def _observer_channel():
    layer = get_channel_layer()
    channel = await layer.new_channel()
    await layer.group_add(OBSERVER_GROUP, channel)
    return layer, channel


async def _collect_public(layer, channel, seconds=1.2):
    """Draine le groupe observateur pendant `seconds` et concatène le stdout."""
    out = b""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while loop.time() < deadline:
        try:
            msg = await asyncio.wait_for(layer.receive(channel), timeout=deadline - loop.time())
        except asyncio.TimeoutError:
            break
        if msg.get("event") == "stdout":
            out += base64.b64decode(msg["data"])
    return out


async def _drain_private(manager, pane_id, contains, timeout=5.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if contains in manager.replay(pane_id):
            return True
        await asyncio.sleep(0.05)
    return False


async def test_compile_redactor_literals_regex_and_invalid():
    redact = compile_redactor([
        ("SECRET_TOKEN", "•••", False),
        (r"sk-[a-z0-9]{8}", "[clé]", True),
        ("([invalide", "x", True),  # regex cassée → ignorée sans planter
        ("", "x", False),
    ])
    out = redact(b"voici SECRET_TOKEN et sk-abcd1234 fin")
    assert b"SECRET_TOKEN" not in out
    assert "•••".encode() in out
    assert b"sk-abcd1234" not in out
    assert b"[cl\xc3\xa9]" in out


async def test_private_pane_never_reaches_observer(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, True)  # live ON mais pane PRIVÉ (défaut)
    layer, channel = await _observer_channel()
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1)

    manager.write(pane.id, b"echo CONTENU_PRIVE_XYZ\n")
    assert await _drain_private(manager, pane.id, b"CONTENU_PRIVE_XYZ")
    public = await _collect_public(layer, channel)
    assert public == b""  # rien, pas même une trame vide
    await manager.kill(pane.id)


async def test_live_off_blocks_public_pane(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, False)  # pane public mais direct COUPÉ
    layer, channel = await _observer_channel()
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1, is_public=True)

    manager.write(pane.id, b"echo PAS_ENCORE_EN_DIRECT\n")
    assert await _drain_private(manager, pane.id, b"PAS_ENCORE_EN_DIRECT")
    assert await _collect_public(layer, channel) == b""
    assert manager.replay_public(pane.id) == b""
    await manager.kill(pane.id)


async def test_public_pane_streams_redacted(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, True)
    layer, channel = await _observer_channel()
    redactor = compile_redactor([("MOT_DE_PASSE_ULTRA", "•••", False)])
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1, is_public=True, redactor=redactor)

    manager.write(pane.id, b"echo avant MOT_DE_PASSE_ULTRA apres\n")
    assert await _drain_private(manager, pane.id, b"MOT_DE_PASSE_ULTRA")
    public = await _collect_public(layer, channel)
    assert b"MOT_DE_PASSE_ULTRA" not in public          # le secret ne sort jamais
    assert "•••".encode() in public                      # remplacé, pas supprimé
    assert b"apres" in public                            # le reste passe
    # Le buffer privé, lui, contient le vrai flux (le cockpit voit tout).
    assert b"MOT_DE_PASSE_ULTRA" in manager.replay(pane.id)
    # Et le replay public est expurgé.
    assert b"MOT_DE_PASSE_ULTRA" not in manager.replay_public(pane.id)
    await manager.kill(pane.id)


async def test_going_public_does_not_reveal_past(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, True)
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1)  # privé

    manager.write(pane.id, b"echo HISTOIRE_PRIVEE\n")
    assert await _drain_private(manager, pane.id, b"HISTOIRE_PRIVEE")

    manager.set_visibility(pane.id, True, owner_id=1)  # passe public APRÈS
    assert b"HISTOIRE_PRIVEE" not in manager.replay_public(pane.id)

    layer, channel = await _observer_channel()
    manager.write(pane.id, b"echo APRES_OUVERTURE\n")
    public = await _collect_public(layer, channel)
    assert b"APRES_OUVERTURE" in public
    assert b"HISTOIRE_PRIVEE" not in public
    await manager.kill(pane.id)


async def test_going_private_forgets_public_buffer(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, True)
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1, is_public=True)
    manager.write(pane.id, b"echo VISIBLE_UN_TEMPS\n")
    assert await _drain_private(manager, pane.id, b"VISIBLE_UN_TEMPS")

    manager.set_visibility(pane.id, False, owner_id=1)
    assert manager.replay_public(pane.id) == b""
    await manager.kill(pane.id)


async def test_set_live_off_purges_public_buffers(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, True)
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1, is_public=True)
    manager.write(pane.id, b"echo EN_DIRECT\n")
    assert await _drain_private(manager, pane.id, b"EN_DIRECT")

    manager.set_live(1, False)
    assert manager.replay_public(pane.id) == b""
    assert pane.buffer_public == bytearray()
    await manager.kill(pane.id)


async def test_refresh_redactor_applies_to_running_panes(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    manager.set_live(1, True)
    layer, channel = await _observer_channel()
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1, is_public=True)

    manager.refresh_redactor(1, compile_redactor([("NOUVEAU_SECRET", "###", False)]))
    manager.write(pane.id, b"echo NOUVEAU_SECRET\n")
    public = await _collect_public(layer, channel)
    assert b"NOUVEAU_SECRET" not in public
    assert b"###" in public
    await manager.kill(pane.id)
