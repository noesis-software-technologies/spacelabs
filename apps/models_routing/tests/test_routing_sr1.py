"""S-R1 — socle du routage (spec MODEL_ROUTING.md §4-6, §9)."""
import json

import httpx
import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.models_routing.adapters import ChatEvent, ContextOverflow, OpenAIHttpAdapter, estimate_tokens
from apps.models_routing.models import MissionTokenBudget, ModelBackend, RoutingRule
from apps.models_routing.router import NoBackendAvailable, record_usage, route
from apps.tasker.models import Mission
from apps.workspaces.models import Workspace
from django.contrib.auth import get_user_model


# ── fixtures locales ─────────────────────────────────────────────────────────
@pytest.fixture
def local_backend(db):
    return ModelBackend.objects.create(
        slug="local-gptoss",
        kind=ModelBackend.KIND_OPENAI_HTTP,
        base_url="http://127.0.0.1:8081/v1",
        model_id="ggml-org/gpt-oss-20b-GGUF",
        context_window=32768,
        max_tokens=4096,
        enabled=True,
        healthy=True,
    )


@pytest.fixture
def claude_backend(db):
    return ModelBackend.objects.create(
        slug="claude-bin",
        kind=ModelBackend.KIND_CLAUDE_BIN,
        context_window=200000,
        max_tokens=8192,
        enabled=True,
        healthy=True,
    )


@pytest.fixture
def mission(db):
    user = get_user_model().objects.create_user(username="po", password="x")
    ws = Workspace.objects.create(owner=user, name="ws", slug="ws")
    return Mission.objects.create(workspace=ws, goal="m1")


# ── routage déterministe ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_route_prend_la_premiere_regle_qui_matche(local_backend, claude_backend):
    """Draft → local ; architecture → claude : la table décide, pas un LLM."""
    RoutingRule.objects.create(order=10, task_class="draft", backend=local_backend)
    RoutingRule.objects.create(order=60, task_class="architecture", backend=claude_backend)

    assert route("draft", est_tokens=500).backend == local_backend
    assert route("architecture", est_tokens=500).backend == claude_backend


@pytest.mark.django_db
def test_route_respecte_le_seuil_de_tokens(local_backend, claude_backend):
    """Au-delà du seuil, la règle locale ne matche plus → règle suivante."""
    RoutingRule.objects.create(order=90, task_class="default", max_est_tokens=6000, backend=local_backend)
    RoutingRule.objects.create(order=99, task_class="default", backend=claude_backend)

    assert route("default", est_tokens=2000).backend == local_backend
    assert route("default", est_tokens=12000).backend == claude_backend


@pytest.mark.django_db
def test_route_saute_les_backends_malades(local_backend, claude_backend):
    """Backend unhealthy → règle suivante (spec §6.3)."""
    local_backend.healthy = False
    local_backend.save(update_fields=["healthy"])
    RoutingRule.objects.create(order=10, task_class="draft", backend=local_backend)
    RoutingRule.objects.create(order=99, task_class="draft", backend=claude_backend)

    assert route("draft", est_tokens=100).backend == claude_backend


@pytest.mark.django_db
def test_route_erreur_franche_sans_backend(local_backend):
    local_backend.enabled = False
    local_backend.save(update_fields=["enabled"])
    RoutingRule.objects.create(order=10, task_class="draft", backend=local_backend)
    with pytest.raises(NoBackendAvailable):
        route("draft", est_tokens=100)


# ── budgets par mission ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_budget_degrade_vers_le_local(local_backend, claude_backend, mission):
    """Budget épuisé + policy degrade → le run part sur le local, flaggé."""
    RoutingRule.objects.create(order=60, task_class="architecture", backend=claude_backend)
    MissionTokenBudget.objects.create(
        mission=mission, budget_tokens=1000, spent_prompt=900, spent_completion=90,
        policy_on_exhaust=MissionTokenBudget.POLICY_DEGRADE,
    )
    decision = route("architecture", est_tokens=500, mission=mission)
    assert decision.backend == local_backend
    assert decision.degraded is True


@pytest.mark.django_db
def test_budget_block_leve_une_erreur(claude_backend, mission):
    RoutingRule.objects.create(order=60, task_class="architecture", backend=claude_backend)
    MissionTokenBudget.objects.create(
        mission=mission, budget_tokens=100, spent_prompt=100,
        policy_on_exhaust=MissionTokenBudget.POLICY_BLOCK,
    )
    with pytest.raises(NoBackendAvailable):
        route("architecture", est_tokens=50, mission=mission)


@pytest.mark.django_db
def test_record_usage_incremente_les_compteurs(mission):
    record_usage(mission, prompt_tokens=120, completion_tokens=30)
    record_usage(mission, prompt_tokens=10, completion_tokens=5)
    # Lecture explicite en base : l'accessor inverse peut servir une
    # instance mise en cache par le premier get_or_create.
    budget = MissionTokenBudget.objects.get(mission=mission)
    assert (budget.spent_prompt, budget.spent_completion) == (130, 35)


# ── sécurité base_url (spec §8) ──────────────────────────────────────────────
@pytest.mark.django_db
def test_base_url_publique_refusee():
    b = ModelBackend(
        slug="evil", kind=ModelBackend.KIND_OPENAI_HTTP, base_url="http://8.8.8.8:80/v1"
    )
    with pytest.raises(ValidationError):
        b.full_clean()


@pytest.mark.django_db
def test_base_url_lan_acceptee(local_backend):
    local_backend.full_clean()  # ne lève pas


# ── adapter OpenAI-compatible (httpx mocké, zéro réseau) ─────────────────────
def _sse_response(chunks):
    body = "\n".join(f"data: {json.dumps(c)}" for c in chunks) + "\ndata: [DONE]\n"
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


@pytest.mark.django_db
async def test_adapter_stream_deltas_et_usage(local_backend):
    chunks = [
        {"choices": [{"delta": {"content": "Bon"}}]},
        {"choices": [{"delta": {"content": "jour"}}]},
        {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 2}},
    ]
    transport = httpx.MockTransport(lambda request: _sse_response(chunks))
    adapter = OpenAIHttpAdapter(local_backend, client=httpx.AsyncClient(transport=transport))

    events = [e async for e in adapter.stream_chat([{"role": "user", "content": "salut"}])]
    text = "".join(e.text for e in events if e.type == "delta")
    usage = next(e for e in events if e.type == "usage")
    assert text == "Bonjour"
    assert usage.data["prompt_tokens"] == 12
    assert events[-1].type == "done"


@pytest.mark.django_db
async def test_adapter_preflight_overflow(local_backend):
    local_backend.context_window = 100
    local_backend.max_tokens = 50
    adapter = OpenAIHttpAdapter(
        local_backend, client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    )
    with pytest.raises(ContextOverflow):
        adapter.preflight([{"role": "user", "content": "x" * 4000}])


@pytest.mark.django_db
async def test_adapter_erreur_http_normalisee(local_backend):
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="down"))
    adapter = OpenAIHttpAdapter(local_backend, client=httpx.AsyncClient(transport=transport))
    events = [e async for e in adapter.stream_chat([{"role": "user", "content": "salut"}])]
    assert events[0].type == "error"
    assert events[0].data["status"] == 503


def test_estimate_tokens_heuristique():
    assert estimate_tokens([{"role": "user", "content": "abcd" * 100}]) == 100


# ── commande health ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_backends_health_marque_ko_sans_serveur(local_backend, capsys):
    """Sans serveur joignable, le backend passe healthy=False (env offline)."""
    local_backend.base_url = "http://127.0.0.1:59999/v1"  # port fermé
    local_backend.save(update_fields=["base_url"])
    call_command("backends_health")
    local_backend.refresh_from_db()
    assert local_backend.healthy is False
    assert local_backend.last_health_at is not None
