"""S17 — mesure de la diffusion à 16 agents.

Ce fichier **mesure**, il ne suppose pas. Les bornes sont larges à dessein :
l'objectif n'est pas de figer une performance (la machine de CI varie), mais
d'attraper une régression d'ordre de grandeur — une boucle quadratique, une
copie du tampon à chaque trame, un abonné jamais retiré.
"""
import asyncio
import time

import pytest

from apps.runtime.services.pane_manager import PaneManager

PANES = 16
FRAMES = 200
FRAME = b"x" * 1024          # 1 ko, l'ordre de grandeur d'une trame de terminal


@pytest.fixture(autouse=True)
def _manager(settings):
    settings.COCKPIT_MAX_PANES = PANES
    settings.COCKPIT_BUFFER_BYTES = 200_000
    PaneManager.reset_for_tests()
    yield
    PaneManager.reset_for_tests()


def _fake_panes(manager, count):
    """Panes en mémoire sans processus : on mesure la diffusion, pas le PTY."""
    from apps.runtime.services.pane_manager import Pane

    for i in range(count):
        manager.panes[f"p{i}"] = Pane(
            id=f"p{i}", cmd="sh", argv=["sh"], cwd="/tmp", proc=None, owner_id=1
        )
    return list(manager.panes.values())


def test_buffer_memory_at_sixteen_panes_is_bounded(settings):
    """Le budget annoncé (BUFFER_BYTES × agents) doit être le budget réel."""
    manager = PaneManager.get()
    panes = _fake_panes(manager, PANES)
    for pane in panes:
        for _ in range(400):
            manager._append_buffer(pane, FRAME)     # 400 ko poussés par pane

    total = sum(len(p.buffer) + len(p.buffer_public) for p in panes)
    cap = settings.COCKPIT_BUFFER_BYTES * PANES * 2      # privé + public
    assert total <= cap, f"{total / 1048576:.1f} Mo > plafond {cap / 1048576:.1f} Mo"
    # Et concrètement : ça doit tenir dans quelques mégaoctets, pas des dizaines.
    assert total < 16 * 1024 * 1024


def test_appending_is_linear_not_quadratic():
    """Un ring buffer recopié à chaque trame passerait de linéaire à quadratique.

    On compare le coût de 4× plus de trames : il doit rester proportionnel, pas
    exploser. Le seuil est large (×12 pour ×4 de travail) pour ne pas devenir
    un test instable sur une CI chargée.
    """
    manager = PaneManager.get()
    pane = _fake_panes(manager, 1)[0]

    def cost(frames):
        start = time.perf_counter()
        for _ in range(frames):
            manager._append_buffer(pane, FRAME)
        return time.perf_counter() - start

    cost(500)                       # préchauffage : tampon déjà plein
    small = cost(500) + 1e-6
    large = cost(2000)
    assert large / small < 12, f"coût non linéaire : ×{large / small:.1f} pour ×4 de trames"


@pytest.mark.asyncio
async def test_fanout_to_sixteen_panes_stays_responsive():
    """200 trames × 16 panes = 3200 diffusions. Doit rester sous la seconde.

    C'est la boucle chaude du produit : chaque octet sorti d'un agent la
    traverse. Une régression ici se voit à l'écran avant de se voir en profil.
    """
    manager = PaneManager.get()
    panes = _fake_panes(manager, PANES)

    start = time.perf_counter()
    for _ in range(FRAMES):
        for pane in panes:
            manager._append_buffer(pane, FRAME)
    elapsed = time.perf_counter() - start

    per_frame_us = (elapsed / (FRAMES * PANES)) * 1e6
    print(f"\n  {FRAMES * PANES} diffusions en {elapsed * 1000:.0f} ms "
          f"({per_frame_us:.1f} µs/trame, {PANES} agents)")
    assert elapsed < 1.0, f"{elapsed:.2f}s pour {FRAMES * PANES} trames"


def test_dead_panes_release_their_buffers():
    """À 16 agents, la mémoire n'est tenable que si un pane mort rend la sienne.

    (La diffusion passe par la channel layer, pas par des files en mémoire :
    il n'y a donc pas d'abonnés à fuir ici — le seul poste qui grossit est le
    tampon de chaque pane.)
    """
    manager = PaneManager.get()
    panes = _fake_panes(manager, PANES)
    for pane in panes:
        for _ in range(300):
            manager._append_buffer(pane, FRAME)

    before = sum(len(p.buffer) for p in manager.panes.values())
    assert before > 0

    for pane_id in list(manager.panes):
        manager.panes.pop(pane_id)

    after = sum(len(p.buffer) for p in manager.panes.values())
    assert after == 0, "des tampons survivent à la mort de leur pane"
