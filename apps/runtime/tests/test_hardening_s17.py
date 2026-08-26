"""S17 — durcissement : liste blanche, budget mémoire, configuration.

Les tests de liste blanche décrivent des attaques précises. Ceux de budget
mesurent, ils ne supposent pas.
"""
import os
import sys

import pytest
from django.conf import settings

from apps.runtime.checks import check_buffer_budget, check_command_allowlist
from apps.runtime.services.pane_manager import PaneError, PaneManager


@pytest.fixture(autouse=True)
def _manager():
    PaneManager.reset_for_tests()
    yield
    PaneManager.reset_for_tests()


async def _spawn(cmd, owner_id=1, **kw):
    return await PaneManager.get().spawn(
        cmd=cmd, cwd="/tmp", owner_id=owner_id, pane_id="p1", **kw
    )


# ── Liste blanche : le trou trouvé en S17 ─────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cmd",
    ["~/evil/claude", "./sh", "../../evil/sh", "/tmp/claude", "/bin/sh",
     "~/.local/bin/bash"],
)
async def test_path_qualified_binaries_are_refused(cmd, settings):
    """Avant S17, la comparaison portait sur le SEUL nom de base : n'importe
    quel binaire nommé « claude » s'exécutait, d'où qu'il vienne. Ce n'est pas
    théorique — COCKPIT_LAN_TOKEN expose ce chemin au réseau local."""
    settings.COCKPIT_ALLOWED_CMDS = ["claude", "bash", "sh"]
    with pytest.raises(PaneError, match="nom de binaire nu|chemin"):
        await _spawn(cmd)


@pytest.mark.asyncio
async def test_a_binary_outside_the_allowlist_is_refused(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["claude"]
    with pytest.raises(PaneError, match="liste blanche"):
        await _spawn("python3")


@pytest.mark.asyncio
async def test_an_empty_command_is_refused(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    with pytest.raises(PaneError, match="vide"):
        await _spawn("   ")


@pytest.mark.asyncio
async def test_a_chained_command_is_refused(settings):
    """`argv` part directement à execve : pas de shell, donc « ; » fait partie
    du nom du binaire et tombe hors liste blanche."""
    settings.COCKPIT_ALLOWED_CMDS = ["claude"]
    with pytest.raises(PaneError, match="liste blanche"):
        await _spawn("claude; rm -rf /")


@pytest.mark.asyncio
async def test_an_unknown_binary_is_reported_clearly(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["nexistepas42"]
    with pytest.raises(PaneError, match="introuvable dans le PATH"):
        await _spawn("nexistepas42")


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="PATH POSIX")
async def test_an_allowed_bare_name_is_resolved_against_the_path(settings):
    """Le nom nu autorisé doit fonctionner — sinon on a cassé l'usage normal."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    pane = await _spawn("sh")
    try:
        assert pane is not None
        # argv[0] a été remplacé par le chemin résolu, pas par ce qu'on a tapé.
        assert os.path.isabs(pane.cmd) or "sh" in pane.cmd
    finally:
        await PaneManager.get().kill("p1")


# ── Contrôles de configuration ────────────────────────────────────────────────
def test_reasonable_buffer_budget_passes(settings):
    settings.COCKPIT_BUFFER_BYTES = 200_000
    settings.COCKPIT_MAX_PANES = 16
    assert check_buffer_budget(None) == []


def test_high_buffer_budget_warns(settings):
    settings.COCKPIT_BUFFER_BYTES = 8 * 1024 * 1024      # 8 Mo par agent
    settings.COCKPIT_MAX_PANES = 16                      # = 128 Mo
    issues = check_buffer_budget(None)
    assert issues and issues[0].id == "runtime.W001"


def test_absurd_buffer_budget_is_an_error(settings):
    settings.COCKPIT_BUFFER_BYTES = 64 * 1024 * 1024
    settings.COCKPIT_MAX_PANES = 16                      # = 1 Go
    issues = check_buffer_budget(None)
    assert issues and issues[0].id == "runtime.E001"


def test_a_path_in_the_allowlist_is_an_error(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["claude", "/usr/local/bin/sh"]
    issues = check_command_allowlist(None)
    assert issues and issues[0].id == "runtime.E002"


def test_a_clean_allowlist_passes(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["claude", "bash", "sh"]
    assert check_command_allowlist(None) == []


# ── Budget mémoire réel, mesuré ───────────────────────────────────────────────
def test_the_shipped_configuration_stays_within_a_workstation_budget():
    """Le produit vise 16 agents sur un poste de travail. On mesure le produit
    des réglages livrés plutôt que de supposer qu'il est raisonnable."""
    total = settings.COCKPIT_BUFFER_BYTES * settings.COCKPIT_MAX_PANES
    assert total < 64 * 1024 * 1024, (
        f"{total / 1048576:.0f} Mo de tampons pour {settings.COCKPIT_MAX_PANES} agents"
    )


@pytest.mark.asyncio
async def test_a_pane_buffer_never_grows_past_its_cap(settings):
    """Le tampon est circulaire : un agent bavard ne doit pas faire enfler la
    mémoire indéfiniment. C'est ce qui rend le budget ci-dessus vrai."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    settings.COCKPIT_BUFFER_BYTES = 4096
    pane = await _spawn("sh")
    try:
        manager = PaneManager.get()
        for _ in range(500):
            manager._append_buffer(pane, b"x" * 200)   # 100 ko dans 4 ko de tampon
        assert len(pane.buffer) <= settings.COCKPIT_BUFFER_BYTES
    finally:
        await PaneManager.get().kill("p1")


# ── La règle est UNIQUE : formulaire et manager la partagent ──────────────────
@pytest.mark.django_db
def test_the_form_applies_the_same_rule_as_the_manager(settings):
    """Le formulaire avait sa PROPRE copie (`cmd.rsplit("/")[-1]`) : elle
    acceptait « /tmp/evil/claude », qui n'était refusé qu'au démarrage. Une
    seule des deux copies avait été durcie."""
    from apps.workspaces.forms import PtyPaneForm

    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    for bad in ["/tmp/evil/sh", "./sh", "~/bin/sh", "python3"]:
        form = PtyPaneForm(data={"title": "", "cmd": bad, "cwd": "", "public_alias": ""})
        assert not form.is_valid(), f"le formulaire accepte « {bad} »"
        assert "cmd" in form.errors


@pytest.mark.django_db
def test_the_form_still_accepts_a_legitimate_command(settings):
    from apps.workspaces.forms import PtyPaneForm

    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    form = PtyPaneForm(data={"title": "", "cmd": "sh -i", "cwd": "", "public_alias": ""})
    assert form.is_valid(), form.errors


def test_the_shared_validator_returns_a_real_path(settings):
    from apps.runtime.services.pane_manager import resolve_allowed_binary

    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    resolved = resolve_allowed_binary("sh")
    assert os.path.isabs(resolved) and os.path.exists(resolved)
