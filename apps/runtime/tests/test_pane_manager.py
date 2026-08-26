"""Tests du cœur PTY — process réels (sh), aucun mock du PTY.

« Ça compile » ≠ « ça marche » (Blueprint §2.11) : on vérifie le roundtrip
stdin→process→stdout, le replay, le kill sans orphelin et les garde-fous.
"""
import asyncio
import os

import pytest

from apps.runtime.services.pane_manager import PaneError, PaneManager

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fresh_manager():
    PaneManager.reset_for_tests()
    yield
    PaneManager.reset_for_tests()


async def _drain(manager, pane_id, contains: bytes, timeout=5.0):
    """Attend que le ring buffer contienne `contains` (la sortie passe par
    add_reader → buffer, indépendamment du channel layer)."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if contains in manager.replay(pane_id):
            return True
        await asyncio.sleep(0.05)
    return False


async def test_spawn_echo_and_stdin_roundtrip(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    pane = await manager.spawn(cmd="sh", cwd="/tmp", cols=80, rows=24)

    manager.write(pane.id, b"echo COCKPIT_$((20+22))\n")
    assert await _drain(manager, pane.id, b"COCKPIT_42")

    await manager.kill(pane.id)
    assert pane.id not in manager.panes


async def test_replay_returns_history(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    pane = await manager.spawn(cmd="sh", cwd="/tmp")
    manager.write(pane.id, b"echo HISTORIQUE_REJOUE\n")
    assert await _drain(manager, pane.id, b"HISTORIQUE_REJOUE")
    # Le replay est la base de la reconnexion : il doit contenir l'historique.
    assert b"HISTORIQUE_REJOUE" in manager.replay(pane.id)
    await manager.kill(pane.id)


async def test_kill_leaves_no_orphan(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    pane = await manager.spawn(cmd="sh", cwd="/tmp")
    pid = pane.proc.pid
    await manager.kill(pane.id)
    # Le process ne doit plus exister (ou être une zombie déjà récoltée).
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_ring_buffer_is_capped(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    settings.COCKPIT_BUFFER_BYTES = 1024
    manager = PaneManager.get()
    pane = await manager.spawn(cmd="sh", cwd="/tmp")
    manager.write(pane.id, b"head -c 8000 /dev/zero | tr '\\0' 'A'; echo FIN_BUFFER\n")
    assert await _drain(manager, pane.id, b"FIN_BUFFER")
    assert len(manager.replay(pane.id)) <= 1024
    await manager.kill(pane.id)


async def test_command_allowlist_enforced(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    with pytest.raises(PaneError, match="liste blanche"):
        await manager.spawn(cmd="python3 -c 'print(1)'")


async def test_max_panes_enforced(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    settings.COCKPIT_MAX_PANES = 2
    manager = PaneManager.get()
    p1 = await manager.spawn(cmd="sh", cwd="/tmp")
    p2 = await manager.spawn(cmd="sh", cwd="/tmp")
    with pytest.raises(PaneError, match="Limite"):
        await manager.spawn(cmd="sh", cwd="/tmp")
    await manager.kill(p1.id)
    await manager.kill(p2.id)


async def test_tenancy_owner_isolation(settings):
    """[TENANCY] par user : un pane d'un autre owner est invisible."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    pane = await manager.spawn(cmd="sh", cwd="/tmp", owner_id=1)
    with pytest.raises(PaneError, match="inconnu"):
        manager.get_pane(pane.id, owner_id=2)
    # Le propriétaire, lui, y accède.
    assert manager.get_pane(pane.id, owner_id=1).id == pane.id
    await manager.kill(pane.id, owner_id=1)


async def test_dead_process_marks_status(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    manager = PaneManager.get()
    pane = await manager.spawn(cmd="sh", cwd="/tmp")
    manager.write(pane.id, b"exit\n")
    deadline = asyncio.get_running_loop().time() + 5
    while pane.status != "dead" and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.05)
    assert pane.status == "dead"
    with pytest.raises(PaneError, match="terminé"):
        manager.write(pane.id, b"echo non\n")
    await manager.kill(pane.id)
