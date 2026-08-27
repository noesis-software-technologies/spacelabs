"""La fixture par défaut charge et route comme la table de la spec (§6)."""
import pytest
from django.core.management import call_command

from apps.models_routing.models import ModelBackend
from apps.models_routing.router import route


@pytest.mark.django_db
def test_fixture_defaults_route_comme_la_spec():
    call_command("loaddata", "routing_defaults")
    # le local est livré healthy=False (tant que le health check n'a pas parlé)
    ModelBackend.objects.filter(slug="local-gptoss").update(healthy=True)

    assert route("draft", 500).backend.slug == "local-gptoss"
    assert route("code_small", 5000).backend.slug == "local-gptoss"
    assert route("architecture", 500).backend.slug == "claude-bin"
    assert route("default", 2000).backend.slug == "local-gptoss"
    assert route("default", 12000).backend.slug == "claude-bin"
