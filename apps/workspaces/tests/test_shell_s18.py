"""Sprint 0 — recomposition du cockpit : contrat de slots + correctif de ciblage.

Ces tests verrouillent le bug signalé (« créer un terminal écrase les partiales »)
et la composition mono-écran : le cockpit se compose dans #content, et aucune
action *in-cockpit* ne vise #content.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.workspaces.models import Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="Alpha", cwd="/tmp")


def test_cockpit_partial_has_stage_dock_and_statusbar(client, user, workspace):
    client.force_login(user)
    url = reverse("workspaces:detail", kwargs={"slug": workspace.slug})
    html = client.get(url, HTTP_HX_REQUEST="true").content.decode()
    assert 'id="stage"' in html            # région de scène swappable
    assert 'id="pane-grid"' in html         # cible d'append des panes
    assert "workspace-statusbar" in html    # barre de statut
    assert "mode-switch" in html            # sélecteur de mode (4 modes)
    assert "workspace-toolbar" in html      # contrat de la vue partielle


def test_create_actions_open_modal_never_content(client, user, workspace):
    """Le bug : créer un pane ciblait #content et écrasait tout le cockpit."""
    client.force_login(user)
    url = reverse("workspaces:detail", kwargs={"slug": workspace.slug})
    html = client.get(url, HTTP_HX_REQUEST="true").content.decode()
    # La création passe par le sélecteur d'agents, ouvert dans la modale.
    picker = reverse("workspaces:agent_picker", kwargs={"slug": workspace.slug})
    assert "data-agent-new" in html
    assert f'hx-get="{picker}"' in html
    assert 'hx-target="#modal"' in html
    # …et #content n'est visé QUE par la navigation de mode (board/swarm/régie).
    assert html.count('hx-target="#content"') == 3


def test_pane_form_appends_to_grid_and_stays_in_modal(client, user, workspace):
    client.force_login(user)
    url = reverse("workspaces:pane_create", kwargs={"slug": workspace.slug, "kind": "pty"})
    resp = client.get(url, HTTP_HX_REQUEST="true")
    html = resp.content.decode()
    assert 'hx-target="#pane-grid"' in html   # succès → ajoute à la grille
    assert 'hx-swap="beforeend"' in html
    assert "#content" not in html             # le formulaire ne touche jamais #content
    assert resp.headers.get("HX-Retarget") == "#modal"   # erreur → reste dans la modale


def test_full_page_keeps_persistent_sidebar(client, user, workspace):
    client.force_login(user)
    url = reverse("workspaces:detail", kwargs={"slug": workspace.slug})
    full = client.get(url).content.decode()
    assert "ds-sidebar" in full   # frame global persistant conservé


def test_pane_create_still_returns_fragment_and_event(client, user, workspace, settings):
    """Le succès reste inchangé : fragment de pane + événement paneCreated."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    client.force_login(user)
    url = reverse("workspaces:pane_create", kwargs={"slug": workspace.slug, "kind": "pty"})
    resp = client.post(url, {"title": "", "cmd": "sh", "cwd": ""}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "data-pane-id" in resp.content.decode()
    assert "paneCreated" in resp.headers.get("HX-Trigger", "")
    # Le succès ne doit PAS être retargeté vers la modale.
    assert "HX-Retarget" not in resp.headers
