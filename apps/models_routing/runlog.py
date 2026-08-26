"""RunLogger — journal append-only des runs routés (spec §4, façon dsh).

Un fichier JSONL par run sous var/runs/ ; la ligne RunLog en base porte les
métadonnées. Le fichier n'est JAMAIS réécrit : replay et audit dérivent du
même flux. Par défaut, pas de payloads complets (spec §8, log_payloads off) —
les deltas sont échantillonnés en compteurs, pas recopiés.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from channels.db import database_sync_to_async
from django.conf import settings
from django.utils import timezone


def runs_dir() -> Path:
    d = Path(settings.BASE_DIR) / "var" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


class RunLogger:
    def __init__(self, run_id: uuid.UUID, path: Path):
        self.run_id = run_id
        self.path = path
        self._t0 = time.monotonic()
        self._deltas = 0

    # ── création ───────────────────────────────────────────────────────────
    @classmethod
    async def start(cls, *, backend, task_class: str, mission=None, decision=None) -> "RunLogger":
        run_id = uuid.uuid4()
        path = runs_dir() / f"{run_id}.jsonl"
        rel = str(path.relative_to(settings.BASE_DIR))

        @database_sync_to_async
        def _create():
            from .models import RunLog

            RunLog.objects.create(
                id=run_id, mission=mission, backend=backend,
                task_class=task_class, status="running", jsonl_path=rel,
            )

        await _create()
        logger = cls(run_id, path)
        await logger.append("run_started", backend=backend.slug, task_class=task_class,
                            mission_id=getattr(mission, "pk", None))
        if decision is not None:
            await logger.append(
                "routed",
                rule=str(decision.rule) if decision.rule else None,
                degraded=decision.degraded, reason=decision.reason,
            )
        return logger

    # ── flux ───────────────────────────────────────────────────────────────
    async def append(self, event_type: str, **fields) -> None:
        line = json.dumps({"t": timezone.now().isoformat(), "type": event_type, **fields},
                          ensure_ascii=False)
        # append-only, flush par ligne — petit volume, simplicité d'audit
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    async def chat_event(self, ev) -> None:
        """Un ChatEvent d'adapter → une trace sobre (pas les payloads)."""
        if ev.type == "delta":
            self._deltas += 1
            return  # échantillonné : compté, pas recopié (log_payloads off)
        if ev.type in ("tool_call", "tool_result"):
            name = (ev.data or {}).get("name", "")
            await self.append(ev.type, name=name)
        elif ev.type == "usage":
            await self.append("usage", **(ev.data or {}))
        elif ev.type == "error":
            await self.append("error", **(ev.data or {}))

    # ── clôture ────────────────────────────────────────────────────────────
    async def finalize(self, status: str, usage: dict | None) -> None:
        duration_ms = int((time.monotonic() - self._t0) * 1000)
        await self.append("run_ended", status=status, deltas=self._deltas,
                          duration_ms=duration_ms)

        @database_sync_to_async
        def _update():
            from .models import RunLog

            RunLog.objects.filter(pk=self.run_id).update(
                status=status, ended_at=timezone.now(), duration_ms=duration_ms,
                prompt_tokens=int((usage or {}).get("prompt_tokens", 0)),
                completion_tokens=int((usage or {}).get("completion_tokens", 0)),
            )

        await _update()
