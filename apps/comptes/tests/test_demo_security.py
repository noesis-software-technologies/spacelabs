from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
@pytest.mark.parametrize("module,debug", [
    ("config.settings.prod", False),
    ("config.settings.prod", True),
    ("config.settings.dev", False),
])
def test_bootstrap_refuses_non_local_settings(settings, module, debug):
    settings.DEBUG = debug
    settings.SETTINGS_MODULE = module
    with pytest.raises(CommandError, match="réservé"):
        call_command("bootstrap_demo", stdout=StringIO())
    assert not get_user_model().objects.exists()


@pytest.mark.django_db
def test_local_bootstrap_preserves_existing_account(settings):
    settings.DEBUG = True
    settings.SETTINGS_MODULE = "config.settings.dev"
    call_command("bootstrap_demo", stdout=StringIO())
    user = get_user_model().objects.get(username="pilote")
    assert user.check_password("cockpit-local")
    assert user.is_superuser
    user.set_password("changed-local-secret")
    user.save(update_fields=["password"])
    previous_hash = user.password
    call_command("bootstrap_demo", stdout=StringIO())
    user.refresh_from_db()
    assert user.password == previous_hash
    assert get_user_model().objects.count() == 1


@pytest.mark.django_db
def test_revoke_known_demo_disables_authentication_and_privileges():
    user = get_user_model().objects.create_superuser("pilote", password="cockpit-local")
    call_command("disable_insecure_demo", stdout=StringIO())
    user.refresh_from_db()
    assert not user.has_usable_password()
    assert not user.is_active
    assert not user.is_staff
    assert not user.is_superuser
    revoked_hash = user.password
    call_command("disable_insecure_demo", stdout=StringIO())
    user.refresh_from_db()
    assert user.password == revoked_hash
    assert get_user_model().objects.count() == 1


@pytest.mark.django_db
def test_revoke_preserves_rotated_account_and_other_users():
    User = get_user_model()
    user = User.objects.create_superuser("pilote", password="rotated-unique-secret")
    other = User.objects.create_superuser("other", password="cockpit-local")
    original_rows = list(User.objects.order_by("pk").values())
    call_command("disable_insecure_demo", stdout=StringIO())
    assert list(User.objects.order_by("pk").values()) == original_rows
    assert user.pk != other.pk


@pytest.mark.django_db
def test_revoke_without_demo_creates_nothing():
    call_command("disable_insecure_demo", stdout=StringIO())
    assert not get_user_model().objects.exists()


def test_public_deploy_does_not_bootstrap_demo():
    render = Path(__file__).resolve().parents[3] / "render.yaml"
    assert "python manage.py bootstrap_demo" not in render.read_text()
