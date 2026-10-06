"""Le boot prod ne dépend pas d'un collectstatic déjà exécuté."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.vitrine import views


def test_prod_boot_collectstatic_and_landing(tmp_path):
    """Un interpréteur neuf charge vraiment les settings et URL de production."""
    static_root = tmp_path / "staticfiles-not-collected"
    env = dict(os.environ)
    env.update(
        DJANGO_SETTINGS_MODULE="config.settings.prod",
        SECRET_KEY="test-only-boot-key-which-is-long-enough-for-django-checks-123456789",
        REDIS_URL="redis://127.0.0.1:6379/15",
        ALLOWED_HOSTS="localhost",
        COCKPIT_TASKER_AUTORUN="False",
    )
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
import json
from pathlib import Path
import django
from django.conf import settings
from django.core.management import call_command
from django.test import RequestFactory

django.setup()
settings.STATIC_ROOT = Path(sys.argv[1])
assert not settings.DEBUG
assert 'CompressedManifestStaticFilesStorage' in settings.STORAGES['staticfiles']['BACKEND']
assert not settings.STATIC_ROOT.exists()
call_command('check', deploy=True)
assert not settings.STATIC_ROOT.exists()
call_command('collectstatic', interactive=False, verbosity=0)
manifest = json.loads((settings.STATIC_ROOT / 'staticfiles.json').read_text())['paths']
for asset in ('vendor/xterm/xterm.js', 'vendor/xterm/addon-fit.js'):
    assert (settings.STATIC_ROOT / manifest[asset]).is_file()
from apps.vitrine.views import landing, PRODUITS
for product in PRODUITS:
    for folder in ('desktop', 'screenshots'):
        asset = f"vitrine/{folder}/{product['slug']}.jpg"
        assert (settings.STATIC_ROOT / manifest[asset]).is_file()
for template in ('clean', 'showroom'):
    request = RequestFactory().get('/', {'template': template}, HTTP_HOST='localhost')
    response = landing(request)
    assert response.status_code == 200
    assert len(response.content) > 1000
""", str(static_root)],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("choice,template", [("clean", "landing.html"), ("showroom", "landing_showroom.html")])
def test_landing_resolves_static_urls_at_render_and_keeps_page_cache(choice, template):
    with override_settings(
        ALLOWED_HOSTS=["testserver"],
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "vitrine-boot-regression"}},
    ):
        cache.clear()
        request = RequestFactory().get("/", {"template": choice})
        with patch.object(views, "static", side_effect=lambda name: f"/assets/{name}") as static_url, \
                patch.object(views, "render", return_value=HttpResponse("landing")) as render:
            assert static_url.call_count == 0
            assert views.landing(request).status_code == 200
            assert static_url.call_count == 2 * len(views.PRODUITS)
            assert render.call_args.args[1] == template
            context = render.call_args.args[2]
            products = json.loads(context["produits_json"])
            assert context["produits_count"] == len(views.PRODUITS)
            assert products[0]["shot"] == f"/assets/vitrine/desktop/{views.PRODUITS[0]['slug']}.jpg"
            assert products[0]["shot_mobile"] == f"/assets/vitrine/screenshots/{views.PRODUITS[0]['slug']}.jpg"
            assert views.landing(request).status_code == 200
            assert render.call_count == 1
            assert static_url.call_count == 2 * len(views.PRODUITS)
        cache.clear()
