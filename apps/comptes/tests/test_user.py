"""AUTH_USER_MODEL custom actif dès J0."""
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model


def test_custom_user_model_is_wired():
    assert settings.AUTH_USER_MODEL == "comptes.User"


@pytest.mark.django_db
def test_bootstrap_demo_is_idempotent(django_user_model):
    from django.core.management import call_command

    call_command("bootstrap_demo")
    call_command("bootstrap_demo")
    assert django_user_model.objects.filter(username="pilote").count() == 1
