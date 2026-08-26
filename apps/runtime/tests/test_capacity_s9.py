"""S9 — capacité « n instances » et capacités du registre.

Chaque test cible un bug précis constaté avant le sprint. Les noms disent
lequel : si l'un d'eux redevient rouge, on sait exactement quelle régression.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.runtime.capacity import (
    CapacityError,
    ensure_can_start,
    owner_limit,
    running_for_owner,
    running_in_workspace,
    workspace_limit,
)
from apps.workspaces.models import HeadlessPane, Pane, PtyPane, Workspace, registry

User = get_user_model()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", password="x")


def _ws(owner, name="W", **kw):
    return Workspace.objects.create(owner=owner, name=name, cwd="~", **kw)


def _running(ws, n, model=HeadlessPane):
    return [model.objects.create(workspace=ws, status=Pane.Status.RUNNING) for _ in range(n)]


# ── Bug n°1 : le plafond était GLOBAL au processus ────────────────────────────
@pytest.mark.django_db
def test_owner_cap_is_not_shared_between_users(alice, bob, settings):
    """Avant S9 : deux comptes à 3 panes saturaient un plafond de 6 commun.

    Le plafond est désormais compté PAR PROPRIÉTAIRE.
    """
    settings.COCKPIT_MAX_PANES = 6
    settings.COCKPIT_OWNER_MAX_PANES = 0  # retombe sur MAX_PANES

    ws_a, ws_b = _ws(alice, "A"), _ws(bob, "B")
    _running(ws_a, 5)
    _running(ws_b, 5)

    # Chacun voit ses 5 agents, pas les 10.
    assert running_for_owner(alice.pk) == 5
    assert running_for_owner(bob.pk) == 5

    # Et chacun peut encore en démarrer un : 10 > 6, mais 5 < 6 chacun.
    ensure_can_start(HeadlessPane.objects.create(workspace=ws_a))
    ensure_can_start(HeadlessPane.objects.create(workspace=ws_b))


# ── Bug n°2 : le headless n'était pas plafonné ────────────────────────────────
@pytest.mark.django_db
def test_cap_counts_headless_too(alice, settings):
    """Avant S9 : seul le PTY était plafonné, on pouvait ouvrir n `claude -p`."""
    settings.COCKPIT_MAX_PANES = 4
    settings.COCKPIT_OWNER_MAX_PANES = 0
    ws = _ws(alice)
    _running(ws, 4, model=HeadlessPane)

    with pytest.raises(CapacityError):
        ensure_can_start(HeadlessPane.objects.create(workspace=ws))


@pytest.mark.django_db
def test_cap_mixes_both_families(alice, settings):
    """Un agent est un agent : 2 PTY + 2 headless saturent un plafond de 4."""
    settings.COCKPIT_MAX_PANES = 4
    settings.COCKPIT_OWNER_MAX_PANES = 0
    ws = _ws(alice)
    _running(ws, 2, model=PtyPane)
    _running(ws, 2, model=HeadlessPane)

    assert running_in_workspace(ws) == 4
    with pytest.raises(CapacityError):
        ensure_can_start(PtyPane.objects.create(workspace=ws, cmd="sh"))


# ── « n instances PAR WORKSPACE » ─────────────────────────────────────────────
@pytest.mark.django_db
def test_workspace_limit_overrides_global(alice, settings):
    settings.COCKPIT_MAX_PANES = 16
    settings.COCKPIT_OWNER_MAX_PANES = 0
    small = _ws(alice, "petit", max_panes=2)
    assert workspace_limit(small) == 2

    _running(small, 2)
    with pytest.raises(CapacityError, match="workspace"):
        ensure_can_start(HeadlessPane.objects.create(workspace=small))


@pytest.mark.django_db
def test_workspace_limit_falls_back_to_setting(alice, settings):
    settings.COCKPIT_MAX_PANES = 16
    assert workspace_limit(_ws(alice)) == 16


@pytest.mark.django_db
def test_sixteen_agents_fit_in_one_workspace(alice, settings):
    """La cible produit : 16 instances dans un workspace."""
    settings.COCKPIT_MAX_PANES = 16
    settings.COCKPIT_OWNER_MAX_PANES = 0
    ws = _ws(alice)
    _running(ws, 15)
    ensure_can_start(HeadlessPane.objects.create(workspace=ws))  # le 16e passe

    _running(ws, 1)  # on y est
    with pytest.raises(CapacityError):
        ensure_can_start(HeadlessPane.objects.create(workspace=ws))


@pytest.mark.django_db
def test_owner_cap_can_be_stricter_than_workspace(alice, settings):
    """Deux workspaces sous le plafond chacun, mais le compte est saturé."""
    settings.COCKPIT_MAX_PANES = 16
    settings.COCKPIT_OWNER_MAX_PANES = 6
    assert owner_limit() == 6

    ws1, ws2 = _ws(alice, "un"), _ws(alice, "deux")
    _running(ws1, 3)
    _running(ws2, 3)

    with pytest.raises(CapacityError, match="compte"):
        ensure_can_start(HeadlessPane.objects.create(workspace=ws2))


@pytest.mark.django_db
def test_restarting_a_running_pane_does_not_count_itself(alice, settings):
    """Relancer le dernier agent ne doit pas échouer : il ne s'ajoute pas."""
    settings.COCKPIT_MAX_PANES = 2
    settings.COCKPIT_OWNER_MAX_PANES = 0
    ws = _ws(alice)
    panes = _running(ws, 2)

    ensure_can_start(panes[-1])  # déjà compté → ne se compte pas deux fois


@pytest.mark.django_db
def test_dead_and_idle_panes_do_not_consume_capacity(alice, settings):
    settings.COCKPIT_MAX_PANES = 2
    settings.COCKPIT_OWNER_MAX_PANES = 0
    ws = _ws(alice)
    HeadlessPane.objects.create(workspace=ws, status=Pane.Status.DEAD)
    HeadlessPane.objects.create(workspace=ws, status=Pane.Status.IDLE)

    assert running_in_workspace(ws) == 0
    ensure_can_start(HeadlessPane.objects.create(workspace=ws))


# ── Bug n°3 : le registre n'avait pas de capacité dispatch ────────────────────
def test_registry_declares_dispatch_for_every_kind():
    """Tout type de pane doit savoir recevoir une consigne (sinon le Tasker
    finirait en `if pane.kind == …`, interdit par §6.9)."""
    for kind, entry in registry.items():
        assert entry.dispatch_path, f"{kind} ne déclare pas de dispatch"
        assert callable(entry.dispatch), f"{kind}: dispatch non résolvable"


def test_only_headless_can_autocomplete():
    """ADR-1 : le PTY n'a pas de signal de fin exploitable (flux ANSI opaque),
    seul le headless émet un `result`."""
    assert registry["headless"].can_autocomplete is True
    assert registry["pty"].can_autocomplete is False


def test_dispatch_is_resolved_lazily():
    """La résolution est paresseuse : importer models ne doit pas tirer runtime
    (import cyclique au chargement des apps)."""
    entry = registry["headless"]
    assert entry.dispatch.__name__ == "headless_dispatch"


def test_unknown_capability_raises_clearly():
    from apps.workspaces.models import RegistryEntry

    entry = RegistryEntry("x", None, "X", "p.html", "m:F")
    with pytest.raises(NotImplementedError, match="dispatch"):
        entry.dispatch


# ── La jauge ne ment plus ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_gauge_limit_matches_the_enforced_limit(alice, settings):
    """Avant S9, la jauge affichait MAX_PANES (plafond PTY) en comptant les
    deux familles. Elle doit lire exactement la limite appliquée."""
    from apps.ops.services import usage_for_owner

    settings.COCKPIT_MAX_PANES = 16
    settings.COCKPIT_OWNER_MAX_PANES = 5
    ws = _ws(alice)
    _running(ws, 3, model=HeadlessPane)

    data = usage_for_owner(alice)
    assert data["max_panes"] == owner_limit() == 5
    assert data["active_panes"] == 3
