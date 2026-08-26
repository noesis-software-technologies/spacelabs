"""Sprint 2 (revamp) — presets d'agents.

Les presets sont une commodité, pas une dérogation : un preset pty passe par
`pane_create` (validation liste-blanche du Sprint 17). Ces tests couvrent la
logique de disponibilité (liste blanche + résolution PATH), le rendu du
sélecteur, le spawn d'un preset disponible, et l'entrée dans la toolbar.

Note : ce conteneur n'a que `bash`/`sh` installés — `claude`/`codex`/`cursor`
ne s'y résolvent pas. Les assertions s'appuient donc sur `bash` (présent) et
évitent de supposer qu'un agent nommé est installé.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.workspaces.agents import presets_with_availability
from apps.workspaces.models import Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="Alpha", cwd="/tmp")


def test_availability_headless_always_and_shell_when_bash_whitelisted(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["bash", "sh"]
    state = {p.key: (a, r) for p, a, r in presets_with_availability()}
    assert state["chat"][0] is True                 # headless : toujours dispo
    assert state["shell"][0] is True                # bash installé + autorisé


def test_availability_unlisted_vs_missing(settings):
    # bash retiré de la liste blanche -> le shell devient "unlisted".
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    state = {p.key: (a, r) for p, a, r in presets_with_availability()}
    assert state["shell"] == (False, "unlisted")
    # codex hors liste blanche -> "unlisted" ; en l'ajoutant (mais absent du
    # conteneur), la raison bascule en "missing" — la liste blanche est bien le
    # premier verrou, la résolution PATH le second.
    settings.COCKPIT_ALLOWED_CMDS = ["sh", "codex"]
    state2 = {p.key: (a, r) for p, a, r in presets_with_availability()}
    assert state2["codex"][1] == "missing"


def test_picker_renders_all_presets_with_disabled(client, user, workspace, settings):
    settings.COCKPIT_ALLOWED_CMDS = ["bash", "sh"]
    client.force_login(user)
    html = client.get(
        reverse("workspaces:agent_picker", kwargs={"slug": workspace.slug}),
        HTTP_HX_REQUEST="true",
    ).content.decode()
    for label in ("Claude Code", "Codex", "Cursor", "Terminal", "Chat Claude"):
        assert label in html, label
    # Au moins une carte disponible poste vers pane_create et vise #pane-grid.
    assert 'hx-target="#pane-grid"' in html
    assert 'hx-swap="beforeend"' in html
    # Et au moins une carte est verrouillée (agents nommés absents du conteneur).
    assert "is-disabled" in html


def test_available_preset_spawns_via_pane_create(client, user, workspace, settings):
    """La carte disponible (shell = bash) crée bien un pane par pane_create."""
    settings.COCKPIT_ALLOWED_CMDS = ["bash", "sh"]
    client.force_login(user)
    url = reverse("workspaces:pane_create", kwargs={"slug": workspace.slug, "kind": "pty"})
    resp = client.post(url, {"cmd": "bash", "title": "Terminal"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "data-pane-id" in resp.content.decode()
    assert "paneCreated" in resp.headers.get("HX-Trigger", "")


def test_toolbar_entry_opens_picker_not_direct_pane(client, user, workspace):
    client.force_login(user)
    html = client.get(
        reverse("workspaces:detail", kwargs={"slug": workspace.slug}), HTTP_HX_REQUEST="true"
    ).content.decode()
    assert "data-agent-new" in html
    assert reverse("workspaces:agent_picker", kwargs={"slug": workspace.slug}) in html
    # La toolbar n'ouvre plus d'URL de création de pane en direct.
    assert "panes/pty/nouveau" not in html
    assert "panes/headless/nouveau" not in html
