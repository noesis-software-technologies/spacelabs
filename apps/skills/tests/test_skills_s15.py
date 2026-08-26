"""S15 — Skills : capitaliser les consignes qui marchent."""
import pytest
from django.contrib.auth import get_user_model

from apps.skills.models import Skill
from apps.skills.services import BUILTINS, SkillError, apply_to_pane, ensure_builtins
from apps.workspaces.models import HeadlessPane, Pane, PtyPane, Workspace

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="W", cwd="/tmp")


@pytest.mark.django_db
def test_builtins_are_seeded_once(user):
    assert ensure_builtins() == len(BUILTINS)
    assert ensure_builtins() == 0, "le seed doit être idempotent"
    assert Skill.objects.filter(is_builtin=True).count() == len(BUILTINS)


@pytest.mark.django_db
def test_builtin_bodies_are_real_instructions():
    ensure_builtins()
    for skill in Skill.objects.filter(is_builtin=True):
        assert len(skill.body) > 60, f"{skill.name} : consigne trop vague"


@pytest.mark.django_db
def test_security_skill_forbids_reading_env_files():
    """Invariant du dépôt : jamais de .env affiché (usage en direct)."""
    ensure_builtins()
    body = Skill.objects.get(name="BridgeSecurity").body
    assert ".env" in body and "jamais" in body.lower()


@pytest.mark.django_db
def test_user_sees_builtins_and_only_their_own(user):
    ensure_builtins()
    other = User.objects.create_user(username="autre", password="x")
    Skill.objects.create(name="À moi", body="x" * 70, owner=user)
    Skill.objects.create(name="À l'autre", body="x" * 70, owner=other)

    names = set(Skill.objects.visible_for(user).values_list("name", flat=True))
    assert "À moi" in names
    assert "À l'autre" not in names
    assert "BridgeSecurity" in names


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_applying_a_skill_dispatches_without_knowing_the_pane_kind():
    """Réutilise la capacité `dispatch` du registre (S9) : aucun if kind ==."""
    from apps.runtime.services.headless_manager import HeadlessManager
    from pathlib import Path

    from django.conf import settings

    settings.COCKPIT_CLAUDE_BIN = str(
        Path(__file__).resolve().parents[2] / "chat" / "tests" / "support" / "fake_claude.py"
    )
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = []
    HeadlessManager.reset_for_tests()

    u = await User.objects.acreate(username="p")
    ws = await Workspace.objects.acreate(owner=u, name="W", cwd="/tmp")
    pane = await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    skill = await Skill.objects.acreate(name="Revue", body="fais une revue", is_builtin=True)

    headless = HeadlessManager.get()
    await headless.start(str(pane.pk), owner_id=u.pk, cwd="/tmp")
    try:
        reply = await apply_to_pane(skill, pane)
        assert "Revue" in reply
    finally:
        await headless.shutdown()
        HeadlessManager.reset_for_tests()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_applying_to_a_pane_without_dispatch_is_refused():
    from apps.workspaces.models import registry

    u = await User.objects.acreate(username="p2")
    ws = await Workspace.objects.acreate(owner=u, name="W", cwd="/tmp")
    pane = await HeadlessPane.objects.acreate(workspace=ws, status=Pane.Status.RUNNING)
    skill = await Skill.objects.acreate(name="X", body="y")

    saved = registry["headless"].dispatch_path
    registry["headless"].dispatch_path = ""
    try:
        with pytest.raises(SkillError):
            await apply_to_pane(skill, pane)
    finally:
        registry["headless"].dispatch_path = saved


@pytest.mark.django_db
def test_endpoint_refuses_an_idle_agent(client, workspace, user):
    ensure_builtins()
    pane = PtyPane.objects.create(workspace=workspace, cmd="sh", status=Pane.Status.IDLE)
    skill = Skill.objects.filter(is_builtin=True).first()
    client.force_login(user)
    r = client.post(f"/skills/{skill.pk}/appliquer/", {"pane": pane.pk})
    assert r.status_code == 409
    assert "démarré" in r.json()["reply"]


@pytest.mark.django_db
def test_endpoint_refuses_someone_elses_pane(client, workspace, user):
    ensure_builtins()
    other = User.objects.create_user(username="autre", password="x")
    other_ws = Workspace.objects.create(owner=other, name="X", cwd="/tmp")
    pane = PtyPane.objects.create(workspace=other_ws, cmd="sh", status=Pane.Status.RUNNING)
    skill = Skill.objects.filter(is_builtin=True).first()
    client.force_login(user)
    assert client.post(f"/skills/{skill.pk}/appliquer/", {"pane": pane.pk}).status_code == 404


@pytest.mark.django_db
def test_panel_lists_skills(client, workspace, user):
    ensure_builtins()
    client.force_login(user)
    html = client.get(f"/skills/w/{workspace.slug}/").content.decode()
    assert "BridgeSecurity" in html and "skill-tag" in html
