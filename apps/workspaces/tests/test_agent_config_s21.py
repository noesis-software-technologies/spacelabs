"""Sprint 3 (revamp) — presets d'agents configurables.

``COCKPIT_AGENT_PRESETS`` (settings / JSON d'env) remplace la liste par défaut.
Ces tests couvrent : le repli sur les défauts, le remplacement, le tri des entrées
invalides, le repli si tout est invalide, le rendu du sélecteur avec des agents
configurés, et le system check qui signale une config mal formée.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.runtime.checks import check_agent_presets
from apps.workspaces.agents import DEFAULT_AGENT_PRESETS, get_agent_presets
from apps.workspaces.models import Workspace


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="Alpha", cwd="/tmp")


# ── Chargement ────────────────────────────────────────────────────────────────
def test_defaults_when_unset(settings):
    settings.COCKPIT_AGENT_PRESETS = []
    assert get_agent_presets() == DEFAULT_AGENT_PRESETS


def test_configured_replaces_defaults(settings):
    settings.COCKPIT_AGENT_PRESETS = [
        {"key": "aider", "label": "Aider", "kind": "pty", "cmd": "aider", "color": "var(--gold)"},
    ]
    presets = {p.key: p for p in get_agent_presets()}
    assert set(presets) == {"aider"}          # les défauts sont remplacés
    assert presets["aider"].label == "Aider"
    assert presets["aider"].cmd == "aider"
    assert presets["aider"].color == "var(--gold)"
    assert presets["aider"].icon == "terminal"   # défaut appliqué
    assert "claude" not in presets


def test_invalid_entries_are_skipped(settings):
    settings.COCKPIT_AGENT_PRESETS = [
        {"key": "ok", "label": "OK", "cmd": "bash"},                 # valide (pty)
        {"key": "", "label": "SansCle", "cmd": "bash"},              # invalide : pas de key
        {"key": "nocmd", "label": "SansCmd", "kind": "pty"},         # invalide : pty sans cmd
        {"key": "bad", "label": "MauvaisKind", "kind": "gui", "cmd": "x"},  # invalide : kind
        {"key": "chatok", "label": "Chat OK", "kind": "headless"},   # valide (headless sans cmd)
    ]
    assert {p.key for p in get_agent_presets()} == {"ok", "chatok"}


def test_all_invalid_falls_back_to_defaults(settings):
    settings.COCKPIT_AGENT_PRESETS = [{"key": "", "label": ""}, "pas un objet"]
    assert get_agent_presets() == DEFAULT_AGENT_PRESETS


# ── System check ──────────────────────────────────────────────────────────────
def test_check_silent_when_unset(settings):
    settings.COCKPIT_AGENT_PRESETS = []
    assert check_agent_presets(None) == []


def test_check_errors_when_not_a_list(settings):
    settings.COCKPIT_AGENT_PRESETS = {"key": "x", "label": "y"}
    problems = check_agent_presets(None)
    assert len(problems) == 1 and problems[0].id == "runtime.E003"


def test_check_warns_on_bad_entries(settings):
    settings.COCKPIT_AGENT_PRESETS = [
        {"key": "ok", "label": "OK", "cmd": "bash"},          # ok
        {"key": "nocmd", "label": "SansCmd", "kind": "pty"},  # pty sans cmd
        {"key": "bad", "label": "X", "kind": "gui", "cmd": "x"},  # kind inconnu
    ]
    problems = check_agent_presets(None)
    assert len(problems) == 2
    assert all(p.id == "runtime.W002" for p in problems)


# ── Rendu du sélecteur ────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_picker_renders_configured_agents(client, user, workspace, settings):
    settings.COCKPIT_AGENT_PRESETS = [
        {"key": "myshell", "label": "Mon Shell", "kind": "pty", "cmd": "bash"},
    ]
    settings.COCKPIT_ALLOWED_CMDS = ["bash", "sh"]
    client.force_login(user)
    html = client.get(
        reverse("workspaces:agent_picker", kwargs={"slug": workspace.slug}),
        HTTP_HX_REQUEST="true",
    ).content.decode()
    assert "Mon Shell" in html
    assert "Claude Code" not in html          # défauts remplacés
    # bash est autorisé + présent -> carte cliquable qui poste vers pane_create
    assert 'hx-target="#pane-grid"' in html
