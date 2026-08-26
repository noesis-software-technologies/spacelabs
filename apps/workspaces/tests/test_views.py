"""Vues workspaces — 2 représentations, permission objet, événements htmx."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.workspaces.models import PtyPane, Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def other():
    return get_user_model().objects.create_user(username="autre", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="Alpha", cwd="/tmp")


def test_home_creates_default_workspace_and_redirects(client, user):
    client.force_login(user)
    response = client.get(reverse("workspaces:home"))
    assert response.status_code == 302
    ws = Workspace.objects.get(owner=user)
    assert ws.name == "Local"
    assert response.url == reverse("workspaces:detail", kwargs={"slug": ws.slug})


def test_detail_two_representations(client, user, workspace):
    client.force_login(user)
    url = reverse("workspaces:detail", kwargs={"slug": workspace.slug})
    full = client.get(url)
    assert full.status_code == 200
    assert "ds-sidebar" in full.content.decode()
    partial = client.get(url, HTTP_HX_REQUEST="true")
    content = partial.content.decode()
    assert "workspace-toolbar" in content
    assert "ds-sidebar" not in content
    assert "HX-Request" in partial.headers.get("Vary", "")


def test_detail_of_other_user_is_404(client, other, workspace):
    client.force_login(other)
    url = reverse("workspaces:detail", kwargs={"slug": workspace.slug})
    assert client.get(url).status_code == 404


def test_create_workspace_htmx_triggers_sidebar_refresh(client, user):
    client.force_login(user)
    response = client.post(
        reverse("workspaces:create"), {"name": "Beta", "cwd": "/tmp"}, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert "workspacesChanged" in response.headers.get("HX-Trigger", "")
    assert Workspace.objects.filter(owner=user, name="Beta").exists()


def test_update_and_delete_workspace(client, user, workspace):
    client.force_login(user)
    client.post(
        reverse("workspaces:update", kwargs={"slug": workspace.slug}),
        {"name": "Alpha 2", "cwd": "/tmp"},
    )
    workspace.refresh_from_db()
    assert workspace.name == "Alpha 2"
    response = client.post(reverse("workspaces:delete", kwargs={"slug": workspace.slug}))
    assert response.status_code == 302
    assert not Workspace.objects.filter(pk=workspace.pk).exists()


def test_pane_create_returns_partial_and_event(client, user, workspace, settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    client.force_login(user)
    url = reverse("workspaces:pane_create", kwargs={"slug": workspace.slug, "kind": "pty"})
    response = client.post(url, {"title": "", "cmd": "sh", "cwd": ""}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    pane = PtyPane.objects.get(workspace=workspace)
    content = response.content.decode()
    assert f'data-pane-id="{pane.pk}"' in content
    assert "paneCreated" in response.headers.get("HX-Trigger", "")


def test_pane_create_rejects_unknown_kind(client, user, workspace):
    client.force_login(user)
    url = reverse("workspaces:pane_create", kwargs={"slug": workspace.slug, "kind": "inconnu"})
    assert client.get(url).status_code == 404


def test_pane_delete_scoped_to_owner(client, user, other, workspace):
    pane = PtyPane.objects.create(workspace=workspace, cmd="sh")
    client.force_login(other)
    url = reverse("workspaces:pane_delete", kwargs={"slug": workspace.slug, "pane_id": pane.pk})
    assert client.post(url).status_code == 404
    client.force_login(user)
    assert client.post(url).status_code == 200
    assert not PtyPane.objects.filter(pk=pane.pk).exists()


def test_detail_query_count_is_bounded(client, user, workspace, django_assert_max_num_queries, settings):
    """Zéro N+1 : 6 panes ne doivent pas faire exploser le nombre de requêtes."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    for _ in range(6):
        PtyPane.objects.create(workspace=workspace, cmd="sh")
    client.force_login(user)
    url = reverse("workspaces:detail", kwargs={"slug": workspace.slug})
    with django_assert_max_num_queries(14):
        client.get(url)


def test_sidebar_partial(client, user, workspace):
    client.force_login(user)
    response = client.get(reverse("workspaces:sidebar"))
    assert response.status_code == 200
    assert "Alpha" in response.content.decode()
