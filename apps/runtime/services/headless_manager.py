"""HeadlessManager — sessions de chat ``claude -p`` en stream-json.

Pendant du PaneManager pour les panes de type chat. Diffère du PTY sur l'IO
(JSON-lignes bidirectionnel via un subprocess asyncio, pas un terminal) mais
partage le MÊME pipeline de diffusion (§2.13) : groupe privé ``pane_{id}`` +
groupe observateur expurgé, gaté par l'état live détenu par le PaneManager.

Persistance intégrale : chaque événement (Claude ou tour humain) est écrit en
EventLog, numéroté et ordonné — c'est la source rejouée à l'attache.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
from typing import Callable

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings

from apps.chat.events import normalize, parse_line, redact_event, user_event

from .pane_manager import OBSERVER_GROUP, PaneError, PaneManager, _noop_redactor

logger = logging.getLogger("spacelabs.headless")


@dataclasses.dataclass
class HeadlessSession:
    id: str
    proc: asyncio.subprocess.Process
    owner_id: int
    is_public: bool = False
    public_label: str = ""
    redact: Callable[[bytes], bytes] = _noop_redactor
    status: str = "running"
    seq: int = 0
    claude_session_id: str | None = None
    public_events: list = dataclasses.field(default_factory=list)
    reader_task: asyncio.Task | None = None

    @property
    def group(self) -> str:
        return f"pane_{self.id}"


@database_sync_to_async
def _store_event(pane_id: int, seq: int, origin: str, event_type: str, payload, normalized):
    from apps.chat.models import EventLog

    EventLog.objects.create(
        pane_id=pane_id, seq=seq, origin=origin,
        event_type=event_type, payload=payload, normalized=normalized,
    )


@database_sync_to_async
def _persist_pane_status(pane_id: int, status: str):
    from apps.workspaces.models import Pane

    Pane.objects.filter(pk=pane_id).update(status=status)


@database_sync_to_async
def _persist_session_id(pane_id: int, session_id: str):
    from apps.workspaces.models import HeadlessPane

    HeadlessPane.objects.filter(pk=pane_id).update(claude_session_id=session_id)


class HeadlessManager:
    _instance: "HeadlessManager | None" = None

    def __init__(self) -> None:
        self.sessions: dict[str, HeadlessSession] = {}

    @classmethod
    def get(cls) -> "HeadlessManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._instance = None

    @staticmethod
    def _build_argv(resume: bool, resume_session_id: str | None) -> list[str]:
        """Args de ``claude -p``. Reprise fidèle par id si disponible, sinon
        --continue (conversation la plus récente du répertoire), sinon rien."""
        argv = [settings.COCKPIT_CLAUDE_BIN, *settings.COCKPIT_CLAUDE_HEADLESS_ARGS]
        if resume and resume_session_id:
            argv[1:1] = ["--resume", resume_session_id]
        elif resume:
            argv.insert(1, "--continue")
        return argv

    # ── cycle de vie ───────────────────────────────────────────────────────
    async def start(
        self, pane_id: str, owner_id: int, cwd: str,
        is_public: bool = False, public_label: str = "", redactor=None,
        resume: bool = False, resume_session_id: str | None = None,
    ) -> HeadlessSession:
        if pane_id in self.sessions and self.sessions[pane_id].status == "running":
            return self.sessions[pane_id]
        if pane_id in self.sessions:
            await self.kill(pane_id)

        # S9 — ce garde-fou n'existait pas : le plafond ne s'appliquait qu'aux
        # PTY alors que la jauge comptait les deux familles. On pouvait ouvrir
        # autant de sessions `claude -p` que voulu.
        mine = sum(
            1 for sess in self.sessions.values()
            if sess.owner_id == owner_id and sess.status == "running" and sess.id != pane_id
        )
        if mine >= settings.COCKPIT_MAX_PANES:
            raise PaneError(f"Limite de {settings.COCKPIT_MAX_PANES} panes atteinte.")

        cwd = os.path.expanduser(cwd or "~")
        if not os.path.isdir(cwd):
            raise PaneError(f"Répertoire introuvable : {cwd}")

        argv = self._build_argv(resume, resume_session_id)
        env = dict(os.environ, TERM="dumb")
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv, cwd=cwd, env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise PaneError(f"Binaire introuvable : {argv[0]}") from exc

        session = HeadlessSession(
            id=pane_id, proc=proc, owner_id=owner_id,
            is_public=is_public, public_label=public_label,
            redact=redactor or _noop_redactor,
        )
        self.sessions[pane_id] = session
        session.reader_task = asyncio.get_running_loop().create_task(self._read_loop(session))
        logger.info("headless %s started pid=%s cwd=%s", pane_id, proc.pid, cwd)
        return session

    async def send(self, pane_id: str, text: str, owner_id: int | None = None) -> None:
        session = self._require(pane_id, owner_id)
        if session.status != "running" or session.proc.stdin is None:
            raise PaneError("Session terminée — impossible d'envoyer.")
        # 1) tour humain : persisté + diffusé (source unique de la bulle user)
        await self._emit(session, user_event(text), origin="user", event_type="user")
        # 2) transmission à Claude au format stream-json
        line = json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }) + "\n"
        session.proc.stdin.write(line.encode())
        await session.proc.stdin.drain()

    async def kill(self, pane_id: str, owner_id: int | None = None) -> None:
        session = self._require(pane_id, owner_id)
        await self._terminate(session)
        self.sessions.pop(pane_id, None)

    async def shutdown(self) -> None:
        for session in list(self.sessions.values()):
            await self._terminate(session)
        self.sessions.clear()

    # ── diffusion (pipeline unique) ────────────────────────────────────────
    async def _read_loop(self, session: HeadlessSession) -> None:
        assert session.proc.stdout is not None
        try:
            while True:
                line = await session.proc.stdout.readline()
                if not line:
                    break
                raw = parse_line(line.decode(errors="replace"))
                if raw is None:
                    continue
                if raw.get("type") == "system" and raw.get("session_id"):
                    if session.claude_session_id != raw["session_id"]:
                        session.claude_session_id = raw["session_id"]
                        await _persist_session_id(int(session.id), raw["session_id"])
                event = normalize(raw)
                if event is None:
                    continue
                await self._emit(session, event, origin="raw",
                                 event_type=raw.get("type", "unknown"), raw_payload=raw)
        finally:
            await self._mark_dead(session)

    async def _emit(self, session, event, origin, event_type, raw_payload=None):
        session.seq += 1
        # Persistance INTÉGRALE : brut pour Claude, événement synthétique sinon.
        await _store_event(
            int(session.id), session.seq, origin, event_type,
            raw_payload if raw_payload is not None else event, event,
        )
        layer = get_channel_layer()
        await layer.group_send(
            session.group,
            {"type": "chat.event", "pane_id": session.id, "seq": session.seq, "event": event},
        )
        if self._public_enabled(session):
            public = redact_event(event, session.redact)
            session.public_events.append({"seq": session.seq, "event": public})
            cap = settings.COCKPIT_MAX_PANES  # borne symbolique du replay public
            if len(session.public_events) > 2000:
                del session.public_events[: len(session.public_events) - 2000]
            await layer.group_send(
                OBSERVER_GROUP,
                {"event": "chat", "pane_id": session.id, "data": public},
            )
            _ = cap

    def _public_enabled(self, session) -> bool:
        return bool(
            session.is_public
            and PaneManager.get().live_by_owner.get(session.owner_id, False)
        )

    async def notify_dead_observer(self, session) -> None:
        if self._public_enabled(session):
            await get_channel_layer().group_send(
                OBSERVER_GROUP, {"event": "status", "pane_id": session.id, "status": "dead"}
            )

    # ── visibilité / live / redaction (mêmes règles que le PTY) ────────────
    def set_visibility(self, pane_id, public, owner_id=None, public_label=None):
        session = self._require(pane_id, owner_id)
        session.is_public = public
        if public_label is not None:
            session.public_label = public_label
        if not public:
            session.public_events.clear()
        return session

    def purge_public(self, owner_id: int) -> None:
        for session in self.sessions.values():
            if session.owner_id == owner_id:
                session.public_events.clear()

    def refresh_redactor(self, owner_id: int, redactor) -> None:
        for session in self.sessions.values():
            if session.owner_id == owner_id:
                session.redact = redactor

    def replay_events(self, pane_id: str):
        """Replay public expurgé (observateur) — jamais les événements privés."""
        session = self.sessions.get(pane_id)
        if session is None or not self._public_enabled(session):
            return []
        return list(session.public_events)

    # ── interne ────────────────────────────────────────────────────────────
    def _require(self, pane_id, owner_id) -> HeadlessSession:
        session = self.sessions.get(pane_id)
        if session is None:
            raise PaneError(f"Session inconnue : {pane_id}")
        if owner_id is not None and session.owner_id != owner_id:
            raise PaneError(f"Session inconnue : {pane_id}")
        return session

    async def _mark_dead(self, session) -> None:
        if session.status == "dead":
            return
        session.status = "dead"
        await _persist_pane_status(int(session.id), "dead")
        await get_channel_layer().group_send(
            session.group, {"type": "chat.status", "pane_id": session.id, "status": "dead"}
        )
        await self.notify_dead_observer(session)
        logger.info("headless %s dead", session.id)

    async def _terminate(self, session) -> None:
        if session.reader_task:
            session.reader_task.cancel()
        proc = session.proc
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()
        for stream in (proc.stdin, proc.stdout):
            transport = getattr(stream, "_transport", None) if stream else None
            if transport is not None:
                try:
                    transport.close()
                except Exception:  # noqa: BLE001 — nettoyage best-effort
                    pass
        session.status = "dead"
        # Persistance directe : le kill annule le reader, dont le `finally`
        # ne peut plus garantir l'écriture du statut.
        await _persist_pane_status(int(session.id), "dead")
