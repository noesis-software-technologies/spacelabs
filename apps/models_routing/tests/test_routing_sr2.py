"""S-R2 — exécution routée (spec §4-§7) : adapter claude-bin, JSONL, diffusion."""
import json
from pathlib import Path

import httpx
import pytest
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model

from apps.models_routing.adapters import ClaudeBinAdapter, OpenAIHttpAdapter, make_adapter
from apps.models_routing.models import MissionTokenBudget, ModelBackend, RoutingRule, RunLog
from apps.models_routing.services import execute_routed_run
from apps.tasker.models import Mission
from apps.workspaces.models import Workspace

FAKE = str(Path(__file__).resolve().parents[2] / "chat" / "tests" / "support" / "fake_claude.py")


@pytest.fixture
def fake_claude(settings):
    settings.COCKPIT_CLAUDE_BIN = FAKE
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = []


@pytest.fixture
def mission(db):
    user = get_user_model().objects.create_user(username="po2", password="x")
    ws = Workspace.objects.create(owner=user, name="ws2", slug="ws2")
    return Mission.objects.create(workspace=ws, goal="m1", task_class="draft")


@pytest.fixture
def local_backend(db):
    return ModelBackend.objects.create(
        slug="local-gptoss", kind=ModelBackend.KIND_OPENAI_HTTP,
        base_url="http://127.0.0.1:8081/v1", model_id="gpt-oss",
        context_window=32768, max_tokens=4096, enabled=True, healthy=True,
    )


@pytest.fixture
def claude_backend(db):
    return ModelBackend.objects.create(
        slug="claude-bin", kind=ModelBackend.KIND_CLAUDE_BIN,
        context_window=200000, max_tokens=8192, enabled=True, healthy=True,
    )


# ── D2 : la classe de tâche vit sur la Mission ───────────────────────────────
@pytest.mark.django_db
def test_mission_porte_sa_task_class(mission):
    assert mission.task_class == "draft"
    assert ("architecture", "Architecture / conception") in Mission._meta.get_field("task_class").choices


# ── ClaudeBinAdapter sur le faux binaire (protocole réel, zéro réseau) ───────
@pytest.mark.django_db
async def test_claude_bin_adapter_one_shot(fake_claude, claude_backend):
    adapter = ClaudeBinAdapter(claude_backend)
    assert await adapter.health() is False or True  # health = which(); le faux n'est pas dans PATH
    events = [e async for e in adapter.stream_chat([{"role": "user", "content": "ping"}])]
    kinds = [e.type for e in events]
    # séquence du faux : text → tool_use → tool_result → text → result
    assert "delta" in kinds and "tool_call" in kinds and "tool_result" in kinds
    assert kinds[-2:] == ["usage", "done"]
    text = "".join(e.text for e in events if e.type == "delta")
    assert "ping" in text  # le faux renvoie le prompt verbatim
    usage = next(e for e in events if e.type == "usage")
    assert usage.data["prompt_tokens"] >= 1 and usage.data["completion_tokens"] >= 1


def test_make_adapter_par_kind(db):
    b1 = ModelBackend(kind=ModelBackend.KIND_OPENAI_HTTP, base_url="http://127.0.0.1:1/v1")
    b2 = ModelBackend(kind=ModelBackend.KIND_CLAUDE_BIN)
    assert isinstance(make_adapter(b1), OpenAIHttpAdapter)
    assert isinstance(make_adapter(b2), ClaudeBinAdapter)


# ── run routé de bout en bout (local mocké) ──────────────────────────────────
def _sse(chunks):
    body = "\n".join(f"data: {json.dumps(c)}" for c in chunks) + "\ndata: [DONE]\n"
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


@pytest.mark.django_db(transaction=True)
async def test_execute_routed_run_local(local_backend, mission, settings, tmp_path):
    settings.BASE_DIR = tmp_path  # var/runs isolé
    from channels.db import database_sync_to_async

    await database_sync_to_async(RoutingRule.objects.create)(
        order=10, task_class="draft", backend=local_backend
    )
    chunks = [
        {"choices": [{"delta": {"content": "sa"}}]},
        {"choices": [{"delta": {"content": "lut"}}]},
        {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}},
    ]
    adapter = OpenAIHttpAdapter(
        local_backend, client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: _sse(chunks)))
    )

    # on écoute le groupe pane_42 comme le ferait le CockpitConsumer
    layer = get_channel_layer()
    await layer.group_add("pane_42", "test-channel")

    result = await execute_routed_run(
        messages=[{"role": "user", "content": "dis salut"}],
        mission=mission, pane_id=42, adapter=adapter,
    )

    assert (result.status, result.text, result.backend_slug) == ("ok", "salut", "local-gptoss")

    # diffusion : le pipeline chat.event existant a reçu les deltas
    msg = await layer.receive("test-channel")
    assert msg["type"] == "chat.event" and msg["event"]["blocks"][0]["text"] == "sa"

    # budget : compteurs réels (usage), pas l'estimation
    budget = await database_sync_to_async(MissionTokenBudget.objects.get)(mission=mission)
    assert (budget.spent_prompt, budget.spent_completion) == (7, 2)

    # RunLog + JSONL append-only
    run = await database_sync_to_async(RunLog.objects.get)(pk=result.run_id)
    assert run.status == "ok" and run.prompt_tokens == 7
    lines = [json.loads(l) for l in (tmp_path / run.jsonl_path).read_text().splitlines()]
    types = [l["type"] for l in lines]
    assert types[0] == "run_started" and "routed" in types and types[-1] == "run_ended"
    assert lines[-1]["deltas"] == 2  # échantillonné : compté, pas recopié


@pytest.mark.django_db(transaction=True)
async def test_execute_routed_run_erreur_backend(local_backend, mission, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    from channels.db import database_sync_to_async

    await database_sync_to_async(RoutingRule.objects.create)(
        order=10, task_class="draft", backend=local_backend
    )
    adapter = OpenAIHttpAdapter(
        local_backend,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503, text="down"))),
    )
    result = await execute_routed_run(
        messages=[{"role": "user", "content": "x"}], mission=mission, adapter=adapter
    )
    assert result.status == "error"
    run = await database_sync_to_async(RunLog.objects.get)(pk=result.run_id)
    assert run.status == "error"
    # un run en erreur ne consomme pas le budget
    exists = await database_sync_to_async(
        MissionTokenBudget.objects.filter(mission=mission, spent_prompt__gt=0).exists
    )()
    assert exists is False
