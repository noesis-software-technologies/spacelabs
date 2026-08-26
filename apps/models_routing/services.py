"""Exécution d'un run routé : route() → adapter → RunLogger → diffusion.

La diffusion réutilise le pipeline EXISTANT du cockpit : messages de type
``chat.event`` sur le groupe ``pane_{id}`` — le handler ``chat_event`` du
CockpitConsumer et le front les affichent sans modification (mêmes formes
normalisées que apps.chat.events).
"""
from __future__ import annotations

import dataclasses

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer

from .adapters import estimate_tokens, make_adapter
from .router import record_usage, route
from .runlog import RunLogger


@dataclasses.dataclass
class RoutedRunResult:
    run_id: str
    backend_slug: str
    status: str
    text: str
    usage: dict
    degraded: bool = False


async def execute_routed_run(
    *,
    messages: list[dict],
    mission=None,
    task_class: str | None = None,
    pane_id: str | int | None = None,
    tools: list | None = None,
    adapter=None,  # hook de test / point d'extension plugin
) -> RoutedRunResult:
    tclass = task_class or getattr(mission, "task_class", None) or "default"
    est = estimate_tokens(messages)
    decision = await database_sync_to_async(route)(tclass, est, mission)
    adapter = adapter or make_adapter(decision.backend)

    runlog = await RunLogger.start(
        backend=decision.backend, task_class=tclass, mission=mission, decision=decision
    )
    layer = get_channel_layer()
    group = f"pane_{pane_id}" if pane_id is not None else None
    seq = 0

    async def _broadcast(event: dict) -> None:
        nonlocal seq
        if group is None:
            return
        seq += 1
        await layer.group_send(
            group, {"type": "chat.event", "pane_id": str(pane_id), "seq": seq, "event": event}
        )

    text_parts: list[str] = []
    usage: dict = {}
    status = "ok"

    async for ev in adapter.stream_chat(messages, tools=tools):
        await runlog.chat_event(ev)
        if ev.type == "delta":
            text_parts.append(ev.text)
            await _broadcast({"kind": "assistant", "blocks": [{"type": "text", "text": ev.text}]})
        elif ev.type == "tool_call":
            await _broadcast({"kind": "assistant", "blocks": [{"type": "tool_use", **(ev.data or {})}]})
        elif ev.type == "tool_result":
            await _broadcast(ev.data or {})
        elif ev.type == "usage":
            usage = ev.data or {}
        elif ev.type == "error":
            status = "error"
            await _broadcast({"kind": "result", "subtype": "error", "is_error": True,
                              "duration_ms": 0, "cost_usd": 0, "num_turns": 0})

    if status == "ok":
        await database_sync_to_async(record_usage)(
            mission, usage.get("prompt_tokens", est), usage.get("completion_tokens", 0)
        )
    await runlog.finalize(status, usage)

    return RoutedRunResult(
        run_id=str(runlog.run_id), backend_slug=decision.backend.slug, status=status,
        text="".join(text_parts), usage=usage, degraded=decision.degraded,
    )
