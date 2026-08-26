"""Vues observer (grille anonyme, régie) et ops consumer S3."""
import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.observer.models import ObserverSettings, RedactionRule
from apps.runtime.routing import websocket_urlpatterns
from apps.runtime.services.pane_manager import PaneManager
from apps.workspaces.models import Pane, PtyPane, Workspace


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="pilote", password="x")


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(owner=user, name="Alpha", cwd="/tmp")


# ── Grille anonyme : LE test de fuite ──────────────────────────────────────
@pytest.mark.django_db
def test_grid_hides_everything_private(client, user, workspace):
    ObserverSettings.objects.create(owner=user, live=True)
    PtyPane.objects.create(workspace=workspace, cmd="claude --secret-arg",
                           cwd="/home/pilote/client-confidentiel", title="ProjetClientX")
    public = PtyPane.objects.create(workspace=workspace, cmd="sh",
                                    cwd="/home/pilote/demo", is_public=True,
                                    public_alias="Démo publique")
    html = client.get(reverse("observer:grid")).content.decode()
    # Le pane privé : placeholder anonyme, rien d'identifiable.
    assert "ProjetClientX" not in html
    assert "client-confidentiel" not in html
    assert "claude --secret-arg" not in html
    assert "Session privée" in html
    # Le pane public : alias uniquement — jamais cmd ni cwd.
    assert "Démo publique" in html
    assert "/home/pilote/demo" not in html
    assert f'data-pane-id="{public.pk}"' in html


@pytest.mark.django_db
def test_grid_standby_when_live_off(client, user, workspace):
    ObserverSettings.objects.create(owner=user, live=False)
    PtyPane.objects.create(workspace=workspace, cmd="sh", is_public=True, public_alias="X")
    html = client.get(reverse("observer:grid")).content.decode()
    assert "En attente du direct" in html
    assert "X" not in html.replace("SpaceLabs", "")  # aucun pane rendu


@pytest.mark.django_db
def test_observer_page_is_anonymous_and_empty_of_data(client, user, workspace):
    PtyPane.objects.create(workspace=workspace, cmd="sh", title="SensibleTitre")
    response = client.get(reverse("observer:page"))
    assert response.status_code == 200
    assert "SensibleTitre" not in response.content.decode()


@pytest.mark.django_db
def test_regie_requires_login_and_lists_rules(client, user):
    assert client.get(reverse("observer:regie")).status_code == 302
    client.force_login(user)
    RedactionRule.objects.create(owner=user, pattern="topsecret")
    html = client.get(reverse("observer:regie")).content.decode()
    assert "topsecret" in html


@pytest.mark.django_db
def test_rule_create_and_delete(client, user):
    client.force_login(user)
    response = client.post(
        reverse("observer:rule_create"),
        {"pattern": "sk-.*", "replacement": "[clé]", "is_regex": "on"},
    )
    assert response.status_code == 200
    rule = RedactionRule.objects.get(owner=user)
    assert rule.is_regex
    response = client.post(reverse("observer:rule_delete", kwargs={"rule_id": rule.pk}))
    assert response.status_code == 200
    assert not RedactionRule.objects.exists()


@pytest.mark.django_db
def test_rule_create_rejects_invalid_regex(client, user):
    client.force_login(user)
    response = client.post(
        reverse("observer:rule_create"),
        {"pattern": "([invalide", "replacement": "x", "is_regex": "on"},
    )
    assert response.status_code == 422
    assert not RedactionRule.objects.exists()


# ── Ops consumer S3 ────────────────────────────────────────────────────────
pytestmark_ws = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def _fresh_manager():
    PaneManager.reset_for_tests()
    yield
    PaneManager.reset_for_tests()


async def _connect(user):
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), "/ws/cockpit/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    return communicator


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_visibility_persists_and_updates_runtime(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await get_user_model().objects.acreate(username="p1")
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    record = await PtyPane.objects.acreate(workspace=ws, cmd="sh")

    c = await _connect(user)
    await c.send_json_to({"op": "spawn", "pane_id": record.pk})
    await c.receive_json_from(timeout=5)

    await c.send_json_to({"op": "set_visibility", "pane_id": record.pk, "public": True})
    for _ in range(20):
        msg = await c.receive_json_from(timeout=5)
        if msg.get("op") == "visibility":
            assert msg["public"] is True
            break
    await record.arefresh_from_db()
    assert record.is_public is True
    assert PaneManager.get().panes[str(record.pk)].is_public is True

    await c.send_json_to({"op": "kill", "pane_id": record.pk})
    await c.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_panic_kills_the_broadcast_everywhere(settings):
    """Panique : live OFF + tous les panes privés, DB ET runtime."""
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await get_user_model().objects.acreate(username="p2")
    await ObserverSettings.objects.acreate(owner=user, live=True)
    ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
    r1 = await PtyPane.objects.acreate(workspace=ws, cmd="sh", is_public=True)
    r2 = await PtyPane.objects.acreate(workspace=ws, cmd="sh", is_public=True)

    c = await _connect(user)
    for r in (r1, r2):
        await c.send_json_to({"op": "spawn", "pane_id": r.pk})
        await c.receive_json_from(timeout=5)

    await c.send_json_to({"op": "panic"})
    for _ in range(20):
        msg = await c.receive_json_from(timeout=5)
        if msg.get("op") == "live":
            assert msg == {"op": "live", "live": False, "panic": True}
            break

    manager = PaneManager.get()
    assert manager.live_by_owner[user.pk] is False
    assert not manager.panes[str(r1.pk)].is_public
    assert not manager.panes[str(r2.pk)].is_public
    async for pane in Pane.objects.filter(workspace=ws):
        assert pane.is_public is False
    settings_obj = await ObserverSettings.objects.aget(owner=user)
    assert settings_obj.live is False

    for r in (r1, r2):
        await c.send_json_to({"op": "kill", "pane_id": r.pk})
    await c.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_set_live_persists(settings):
    settings.COCKPIT_ALLOWED_CMDS = ["sh"]
    user = await get_user_model().objects.acreate(username="p3")
    c = await _connect(user)
    await c.send_json_to({"op": "set_live", "live": True})
    msg = await c.receive_json_from(timeout=5)
    assert msg == {"op": "live", "live": True}
    settings_obj = await ObserverSettings.objects.aget(owner=user)
    assert settings_obj.live is True
    assert PaneManager.get().live_by_owner[user.pk] is True
    await c.disconnect()
