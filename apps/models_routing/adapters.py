"""Contrat de backend (« tout est plugin ») + adapter OpenAI-compatible.

S-R1 : seul OpenAIHttpAdapter est implémenté ; ClaudeBinAdapter (enveloppe du
runner headless existant) arrive en S-R2 — on adapte l'existant, on ne le
réécrit pas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator, Iterable, Protocol

import httpx


# ── Événements normalisés ────────────────────────────────────────────────────
@dataclass
class ChatEvent:
    type: str  # "delta" | "tool_call" | "usage" | "done" | "error"
    text: str = ""
    data: dict | None = None


def estimate_tokens(messages: Iterable[dict]) -> int:
    """Heuristique volontairement simple (chars/4) — pré-vol overflow et
    seuils de routage. Pas de tokenizer lourd côté plan de contrôle."""
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    return max(total_chars // 4, 1)


class ModelBackendAdapter(Protocol):  # pragma: no cover - contrat
    async def health(self) -> bool: ...

    def stream_chat(
        self, messages: list[dict], tools: list | None = None, max_tokens: int | None = None
    ) -> AsyncIterator[ChatEvent]: ...


class ContextOverflow(Exception):
    """Le prompt estimé ne tient pas dans context_window - max_tokens."""


# ── OpenAI-compatible (llama-server, vLLM, …) ───────────────────────────────
class OpenAIHttpAdapter:
    def __init__(self, backend, client: httpx.AsyncClient | None = None):
        self.backend = backend
        # timeout long : cold start + générations locales lentes (spec §5)
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))

    async def health(self) -> bool:
        try:
            resp = await self._client.get(f"{self.backend.base_url.rstrip('/')}/models")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def preflight(self, messages: list[dict], max_tokens: int | None = None) -> int:
        est = estimate_tokens(messages)
        reserve = max_tokens or self.backend.max_tokens
        if est > self.backend.context_window - reserve:
            raise ContextOverflow(
                f"prompt estimé {est} tok > budget {self.backend.context_window - reserve}"
            )
        return est

    async def stream_chat(
        self, messages: list[dict], tools: list | None = None, max_tokens: int | None = None
    ) -> AsyncIterator[ChatEvent]:
        self.preflight(messages, max_tokens)
        payload: dict = {
            "model": self.backend.model_id,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens or self.backend.max_tokens,
            # les compteurs réels arrivent dans le dernier chunk SSE
            "stream_options": {"include_usage": True},
        }
        if tools and self.backend.supports_tools:
            payload["tools"] = tools

        url = f"{self.backend.base_url.rstrip('/')}/chat/completions"
        try:
            async with self._client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")[:300]
                    yield ChatEvent("error", data={"status": resp.status_code, "body": body})
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("usage"):
                        yield ChatEvent("usage", data=obj["usage"])
                    for choice in obj.get("choices", []):
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            yield ChatEvent("delta", text=delta["content"])
                        if delta.get("tool_calls"):
                            yield ChatEvent("tool_call", data={"tool_calls": delta["tool_calls"]})
        except httpx.HTTPError as exc:
            yield ChatEvent("error", data={"exception": type(exc).__name__, "detail": str(exc)})
            return
        yield ChatEvent("done")

    async def aclose(self):  # pragma: no cover - plomberie
        await self._client.aclose()


# ── Binaire claude (abonnement) — one-shot routé ────────────────────────────
class ClaudeBinAdapter:
    """Enveloppe ONE-SHOT du binaire ``claude -p`` pour les runs routés.

    Réutilise le protocole et le parsing EXISTANTS (apps.chat.events) — même
    argv que HeadlessManager, même stream-json. Les sessions longues des panes
    restent l'affaire du HeadlessManager ; ici : un tour, une réponse, exit
    (stdin fermé après le tour ⇒ le binaire termine après son result).
    """

    def __init__(self, backend):
        self.backend = backend

    async def health(self) -> bool:
        import shutil
        from django.conf import settings

        return shutil.which(settings.COCKPIT_CLAUDE_BIN) is not None

    def preflight(self, messages: list[dict], max_tokens: int | None = None) -> int:
        return estimate_tokens(messages)  # fenêtre 200k : pas de garde utile ici

    async def stream_chat(
        self, messages: list[dict], tools: list | None = None, max_tokens: int | None = None
    ) -> AsyncIterator[ChatEvent]:
        import asyncio
        import os

        from django.conf import settings

        from apps.chat.events import normalize, parse_line

        prompt = next(
            (str(m.get("content", "")) for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        argv = [settings.COCKPIT_CLAUDE_BIN, *settings.COCKPIT_CLAUDE_HEADLESS_ARGS]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=dict(os.environ, TERM="dumb"),
            )
        except FileNotFoundError:
            yield ChatEvent("error", data={"exception": "FileNotFoundError", "detail": argv[0]})
            return

        turn = json.dumps(
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}]}}
        ) + "\n"
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(turn.encode())
        await proc.stdin.drain()
        proc.stdin.close()  # un seul tour : EOF ⇒ le binaire sort après result

        completion_chars = 0
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                raw = parse_line(line.decode(errors="replace"))
                if raw is None:
                    continue
                event = normalize(raw)
                if event is None:
                    continue
                if event["kind"] == "assistant":
                    for block in event["blocks"]:
                        if block["type"] == "text":
                            completion_chars += len(block["text"])
                            yield ChatEvent("delta", text=block["text"])
                        elif block["type"] == "tool_use":
                            yield ChatEvent("tool_call", data=block)
                elif event["kind"] == "tool_result":
                    yield ChatEvent("tool_result", data=event)
                elif event["kind"] == "result":
                    usage = (raw.get("usage") or {}) if isinstance(raw, dict) else {}
                    yield ChatEvent(
                        "usage",
                        data={
                            "prompt_tokens": usage.get("input_tokens", estimate_tokens(messages)),
                            "completion_tokens": usage.get("output_tokens", max(completion_chars // 4, 1)),
                            "estimated": "input_tokens" not in usage,
                            "cost_usd": event.get("cost_usd", 0),
                            "duration_ms": event.get("duration_ms", 0),
                        },
                    )
                    break
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
        yield ChatEvent("done")


def make_adapter(backend):
    """Fabrique par kind — le point d'extension « tout est plugin »."""
    if backend.kind == "openai_http":
        return OpenAIHttpAdapter(backend)
    if backend.kind == "claude_bin":
        return ClaudeBinAdapter(backend)
    raise ValueError(f"kind de backend inconnu : {backend.kind}")
