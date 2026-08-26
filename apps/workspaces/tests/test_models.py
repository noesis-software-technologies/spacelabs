"""Modèles workspaces — slug, labels d'agents, MTI + registre, tenancy."""
import pytest
from django.contrib.auth import get_user_model

from apps.workspaces.forms import PtyPaneForm, WorkspaceForm
from apps.workspaces.models import (
    AGENT_NAMES,
    HeadlessPane,
    Pane,
    PtyPane,
    Workspace,
    form_for,
    registry,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="Mon Projet", cwd="/tmp")


def test_slug_auto_and_unique_per_owner(user):
    a = Workspace.objects.create(owner=user, name="Mon Projet", cwd="/tmp")
    b = Workspace.objects.create(owner=user, name="Mon Projet", cwd="/tmp")
    assert a.slug == "mon-projet"
    assert b.slug == "mon-projet-2"


def test_agent_labels_auto_and_distinct(workspace):
    p1 = PtyPane.objects.create(workspace=workspace, cmd="sh")
    p2 = PtyPane.objects.create(workspace=workspace, cmd="sh")
    assert p1.title == AGENT_NAMES[0]
    assert p2.title == AGENT_NAMES[1]
    assert p1.kind == "pty"


def test_registry_polymorphism(workspace):
    """Gate §6.9 : le pipeline ne connaît que la base + le registre."""
    PtyPane.objects.create(workspace=workspace, cmd="sh")
    HeadlessPane.objects.create(workspace=workspace)
    kinds = {p.kind for p in Pane.objects.all()}
    assert kinds == {"pty", "headless"}
    for pane in Pane.objects.all():
        entry = registry[pane.kind]
        concrete = pane.concrete
        assert isinstance(concrete, entry.model)
        assert entry.partial.startswith("workspaces/partials/_pane_")
        assert form_for(pane.kind)  # form résolue sans toucher au pipeline


def test_tenancy_for_owner(user, workspace):
    other = get_user_model().objects.create_user(username="autre", password="x")
    Workspace.objects.create(owner=other, name="Ailleurs", cwd="/tmp")
    assert Workspace.objects.for_owner(user).count() == 1
    PtyPane.objects.create(workspace=workspace, cmd="sh")
    assert Pane.objects.for_owner(user).count() == 1
    assert Pane.objects.for_owner(other).count() == 0


def test_respawn_cmd_appends_continue_for_claude(workspace):
    pane = PtyPane.objects.create(workspace=workspace, cmd="claude")
    assert pane.respawn_cmd() == "claude --continue"
    pane2 = PtyPane.objects.create(workspace=workspace, cmd="claude --continue")
    assert pane2.respawn_cmd() == "claude --continue"      # idempotent
    pane3 = PtyPane.objects.create(workspace=workspace, cmd="sh")
    assert pane3.respawn_cmd() == "sh"                      # jamais pour un shell


def test_workspace_form_rejects_missing_dir():
    form = WorkspaceForm(data={"name": "X", "cwd": "/definitivement/inexistant"})
    assert not form.is_valid()
    assert "cwd" in form.errors


def test_pane_form_enforces_allowlist(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["claude", "sh"]
    ok = PtyPaneForm(data={"title": "", "cmd": "sh -l", "cwd": ""})
    assert ok.is_valid(), ok.errors
    ko = PtyPaneForm(data={"title": "", "cmd": "python3 evil.py", "cwd": ""})
    assert not ko.is_valid()
    assert "liste blanche" in str(ko.errors["cmd"])


def test_effective_cwd_falls_back_to_workspace(workspace):
    pane = PtyPane.objects.create(workspace=workspace, cmd="sh")
    assert pane.effective_cwd() == "/tmp"
    pane.cwd = "/var"
    assert pane.effective_cwd() == "/var"
