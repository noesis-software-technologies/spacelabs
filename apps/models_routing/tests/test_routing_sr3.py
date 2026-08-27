"""S-R3 — UI (statusbar/régie) + calibration des seuils (spec §6-§7)."""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from apps.models_routing.management.commands.calibrate_thresholds import derive_threshold
from apps.models_routing.models import MissionTokenBudget, ModelBackend, RoutingRule, RunLog
from apps.tasker.models import Mission
from apps.workspaces.models import Workspace


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(username="pilote3", password="x")


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(owner=owner, name="ws3", slug="ws3")


@pytest.fixture
def mission(workspace):
    return Mission.objects.create(workspace=workspace, goal="m", task_class="draft")


@pytest.fixture
def backend(db):
    return ModelBackend.objects.create(
        slug="local-gptoss", kind=ModelBackend.KIND_OPENAI_HTTP,
        base_url="http://127.0.0.1:8081/v1", context_window=32768, max_tokens=4096,
        enabled=True, healthy=True,
    )


def _run(mission, backend, **kw):
    return RunLog.objects.create(
        id=uuid.uuid4(), mission=mission, backend=backend, task_class="draft",
        status="ok", prompt_tokens=7, completion_tokens=2, duration_ms=1200,
        jsonl_path="var/runs/x.jsonl", **kw,
    )


# ── statusbar ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_statusbar_affiche_backend_et_budget(client, owner, workspace, mission, backend):
    _run(mission, backend)
    MissionTokenBudget.objects.create(mission=mission, budget_tokens=50000,
                                      spent_prompt=3000, spent_completion=200)
    client.force_login(owner)
    html = client.get(reverse("models_routing:statusbar", args=[workspace.slug])).content.decode()
    assert "local-gptoss" in html and "3200/50000" in html


@pytest.mark.django_db
def test_statusbar_refuse_le_workspace_d_autrui(client, workspace, mission, backend):
    intrus = get_user_model().objects.create_user(username="intrus", password="x")
    client.force_login(intrus)
    assert client.get(reverse("models_routing:statusbar", args=[workspace.slug])).status_code == 404


# ── panneau régie ────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_runs_panel_liste_mes_runs(client, owner, workspace, mission, backend):
    _run(mission, backend)
    client.force_login(owner)
    html = client.get(reverse("models_routing:runs")).content.decode()
    assert "local-gptoss" in html and "7+2" in html and "var/runs/x.jsonl" in html


# ── calibration : la règle de la spec §6 en chiffres ─────────────────────────
def test_derive_threshold_regle_du_budget_temps():
    # pp=200 tok/s, gen=20 tok/s, budget 90 s : 400 tok de réponse = 20 s,
    # reste 70 s de prompt processing → 14 000 tokens de prompt max.
    assert derive_threshold(200, 20, 90) == 14000
    # borné par le budget prompt du backend
    assert derive_threshold(200, 20, 90, prompt_budget=8000) == 8000
    # génération trop lente pour le budget → 0 (le local ne prend rien)
    assert derive_threshold(200, 2, 90) == 0


@pytest.mark.django_db
def test_calibrate_command_met_a_jour_les_regles(backend, monkeypatch):
    RoutingRule.objects.create(order=40, task_class="code_small",
                               max_est_tokens=8000, backend=backend)
    RoutingRule.objects.create(order=10, task_class="draft", backend=backend)  # sans seuil

    async def fake_measure(b, prompt_tokens_target=1500):
        return 200.0, 20.0

    monkeypatch.setattr(
        "apps.models_routing.management.commands.calibrate_thresholds.measure_backend",
        fake_measure,
    )
    call_command("calibrate_thresholds")

    seuil = RoutingRule.objects.get(task_class="code_small").max_est_tokens
    # min(14000, prompt_budget=32768-4096=28672) = 14000
    assert seuil == 14000
    # la règle sans seuil reste illimitée (on ne cale que celles qui en portent)
    assert RoutingRule.objects.get(task_class="draft").max_est_tokens is None
