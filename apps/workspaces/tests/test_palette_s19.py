"""Sprint 1 (revamp) — palette de commandes ⌘K.

La liste est construite côté client à partir des contrôles présents ; ces tests
verrouillent donc (1) la coquille de la palette et son script, (2) le déclencheur
dans la toolbar, et surtout (3) que chaque cible déclenchée par la palette existe
réellement dans le cockpit — sinon une commande deviendrait un clic dans le vide.
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


def test_palette_shell_and_script_on_full_page(client, user, workspace):
    client.force_login(user)
    full = client.get(reverse("workspaces:detail", kwargs={"slug": workspace.slug})).content.decode()
    assert 'id="palette"' in full
    assert 'id="palette-input"' in full
    assert 'id="palette-list"' in full
    assert "js/palette.js" in full


def test_palette_trigger_in_toolbar(client, user, workspace):
    client.force_login(user)
    partial = client.get(
        reverse("workspaces:detail", kwargs={"slug": workspace.slug}), HTTP_HX_REQUEST="true"
    ).content.decode()
    assert "data-palette-open" in partial


def test_palette_targets_all_exist_in_cockpit(client, user, workspace):
    client.force_login(user)
    html = client.get(
        reverse("workspaces:detail", kwargs={"slug": workspace.slug}), HTTP_HX_REQUEST="true"
    ).content.decode()
    # Contrôles visés par la palette (sel) — chacun doit être présent.
    for hook in (
        'data-mode="terminals"', 'data-mode="board"', 'data-mode="swarm"',
        "data-agent-new", "data-spawn-all", "data-live-toggle", "data-panic",
        "data-rail-toggle", "data-dock-toggle", 'data-density-set="dense"',
    ):
        assert hook in html, hook
    # Onglets du dock (commandes run : Skills / Éditeur / Bridge).
    for tab in ('data-tab="skills"', 'data-tab="editor"', 'data-tab="bridge"'):
        assert tab in html, tab
