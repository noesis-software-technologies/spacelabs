"""Garde par jeton LAN + drapeau de reprise au boot."""
import pytest
from django.contrib.auth import get_user_model

from apps.common.middleware import COOKIE
from apps.ops.services import reconcile_boot
from apps.workspaces.models import Pane, PtyPane, Workspace


# ── Middleware token LAN ───────────────────────────────────────────────────
@pytest.mark.django_db
def test_no_token_configured_allows_everything(client, settings):
    settings.COCKPIT_LAN_TOKEN = ""
    assert client.get("/healthz").status_code == 200
    # une page publique quelconque n'est pas bloquée
    assert client.get("/observer/").status_code == 200


@pytest.mark.django_db
def test_token_configured_blocks_without_token(client, settings):
    settings.COCKPIT_LAN_TOKEN = "sesame"
    r = client.get("/observer/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_healthz_and_static_exempt(client, settings):
    settings.COCKPIT_LAN_TOKEN = "sesame"
    assert client.get("/healthz").status_code == 200
    assert client.get(settings.STATIC_URL + "js/shell.js").status_code in (200, 404)


@pytest.mark.django_db
def test_query_token_sets_cookie_and_allows(client, settings):
    settings.COCKPIT_LAN_TOKEN = "sesame"
    r = client.get("/observer/?token=sesame")
    assert r.status_code == 200
    assert client.cookies.get(COOKIE).value == "sesame"
    # cookie posé ⇒ requête suivante sans query passe
    assert client.get("/observer/").status_code == 200


@pytest.mark.django_db
def test_wrong_token_blocked(client, settings):
    settings.COCKPIT_LAN_TOKEN = "sesame"
    assert client.get("/observer/?token=nope").status_code == 403


# ── Reprise au boot ────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_reconcile_flags_resume_when_enabled(settings):
    settings.COCKPIT_RESUME_ON_BOOT = True
    user = get_user_model().objects.create_user(username="p", password="x")
    ws = Workspace.objects.create(owner=user, name="A", cwd="/tmp")
    pane = PtyPane.objects.create(workspace=ws, cmd="sh",
                                  status=Pane.Status.RUNNING, runtime_boot_id="ancienne")
    reconcile_boot("courante")
    pane.refresh_from_db()
    assert pane.status == Pane.Status.DEAD
    assert pane.resume_pending is True


@pytest.mark.django_db
def test_reconcile_no_resume_flag_when_disabled(settings):
    settings.COCKPIT_RESUME_ON_BOOT = False
    user = get_user_model().objects.create_user(username="p", password="x")
    ws = Workspace.objects.create(owner=user, name="A", cwd="/tmp")
    pane = PtyPane.objects.create(workspace=ws, cmd="sh",
                                  status=Pane.Status.RUNNING, runtime_boot_id="ancienne")
    reconcile_boot("courante")
    pane.refresh_from_db()
    assert pane.status == Pane.Status.DEAD
    assert pane.resume_pending is False
