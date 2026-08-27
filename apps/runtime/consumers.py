"""Consumer WebSocket du cockpit — un socket par client, multiplexé par pane_id.

Sprint 2 : les panes existent en base AVANT tout spawn (créés via htmx).
Le protocole référence donc toujours un ``pane_id`` persistant — la
corrélation client/serveur est structurelle, plus besoin de slot "spawned".

Blueprint §2.8 : auth obligatoire (4401 sinon) et autorisation objet
(workspace.owner) AVANT tout ``group_add``.

Protocole (JSON, data en base64) :
  C→S : {op: "spawn",  pane_id, continue?: bool}   # continue → respawn_cmd()
        {op: "attach", pane_id}
        {op: "stdin",  pane_id, data}
        {op: "resize", pane_id, cols, rows}
        {op: "kill",   pane_id}
  S→C : {op: "stdout", pane_id, data}              # base64
        {op: "status", pane_id, status}
        {op: "error",  message, pane_id?}
"""
from __future__ import annotations

import base64
import binascii
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.observer.models import ObserverSettings
from apps.observer.redaction import redactor_for_rules_qs
from apps.workspaces.models import HeadlessPane, Pane, PtyPane

from .capacity import CapacityError, ensure_can_start
from .runtime_state import BOOT_ID
from .services.headless_manager import HeadlessManager
from .services.pane_manager import PaneError, PaneManager

logger = logging.getLogger("spacelabs.runtime")

MAX_STDIN_BYTES = 8192


@database_sync_to_async
def _load_pty_pane(pane_id, owner_id) -> PtyPane:
    try:
        return PtyPane.objects.select_related("workspace").get(
            pk=pane_id, workspace__owner_id=owner_id
        )
    except (PtyPane.DoesNotExist, ValueError) as exc:
        raise PaneError(f"Pane inconnu : {pane_id}") from exc


@database_sync_to_async
def _check_capacity(pane) -> None:
    """Plafonds par workspace et par compte — POINT D'APPLICATION UNIQUE.

    Appelé pour les deux familles (PTY et headless) : c'est ce qui corrige le
    plafond qui ne s'appliquait qu'aux PTY (S9, cf. apps/runtime/capacity.py).
    """
    ensure_can_start(pane)


@database_sync_to_async
def _persist_status(pane_id, status) -> None:
    Pane.objects.filter(pk=pane_id).update(status=status)


@database_sync_to_async
def _stamp_running(pane_id) -> None:
    """Passe le pane en RUNNING et l'estampille avec la génération Daphne
    courante — c'est cette marque qui distingue un vivant d'un zombie."""
    Pane.objects.filter(pk=pane_id).update(
        status=Pane.Status.RUNNING, runtime_boot_id=BOOT_ID, resume_pending=False
    )


@database_sync_to_async
def _persist_visibility(pane_id, public) -> None:
    Pane.objects.filter(pk=pane_id).update(is_public=public)


@database_sync_to_async
def _load_base_pane(pane_id, owner_id):
    try:
        return Pane.objects.select_related("workspace").get(
            pk=pane_id, workspace__owner_id=owner_id
        )
    except (Pane.DoesNotExist, ValueError) as exc:
        raise PaneError(f"Pane inconnu : {pane_id}") from exc


@database_sync_to_async
def _load_headless_pane(pane_id, owner_id):
    try:
        return HeadlessPane.objects.select_related("workspace").get(
            pk=pane_id, workspace__owner_id=owner_id
        )
    except (HeadlessPane.DoesNotExist, ValueError) as exc:
        raise PaneError(f"Pane inconnu : {pane_id}") from exc


@database_sync_to_async
def _clear_session_id(pane_id):
    from apps.workspaces.models import HeadlessPane

    HeadlessPane.objects.filter(pk=pane_id).update(claude_session_id="")


@database_sync_to_async
def _replay_events(pane_id):
    from apps.chat.models import EventLog

    return list(
        EventLog.objects.filter(pane_id=pane_id).order_by("seq")
        .values_list("seq", "normalized")
    )


@database_sync_to_async
def _load_owner_context(owner_id):
    """Live + redactor compilé de l'opérateur (chargés au spawn / à la demande)."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get(pk=owner_id)
    live = ObserverSettings.for_owner(user).live
    redactor = redactor_for_rules_qs(user.redaction_rules)
    return live, redactor


@database_sync_to_async
def _persist_live(owner_id, live) -> None:
    ObserverSettings.objects.update_or_create(owner_id=owner_id, defaults={"live": live})


@database_sync_to_async
def _panic_persist(owner_id) -> list[int]:
    """Panique : live OFF + TOUS les panes de l'owner repassent privés.
    Retourne les pks affectés pour resynchroniser le runtime."""
    ObserverSettings.objects.update_or_create(owner_id=owner_id, defaults={"live": False})
    pks = list(Pane.objects.filter(workspace__owner_id=owner_id).values_list("pk", flat=True))
    Pane.objects.filter(pk__in=pks).update(is_public=False)
    return pks


class CockpitConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # La boucle d'orchestration vit dans CE processus (celui qui possède
        # les managers). On la démarre à la première connexion : à l'import de
        # asgi.py il n'y a pas encore de boucle asyncio. Idempotent.
        try:
            from apps.tasker.runner import start as _start_tasker

            _start_tasker()
        except Exception:  # noqa: BLE001 — l'orchestration ne doit jamais bloquer un socket
            logger.debug("boucle d'orchestration non démarrée", exc_info=True)
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.user = user
        self.joined_groups: set[str] = set()
        self.manager = PaneManager.get()
        self.headless = HeadlessManager.get()
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, "joined_groups", set()):
            await self.channel_layer.group_discard(group, self.channel_name)
        # Les panes survivent à la déconnexion (reprise/replay à l'attach).

    # ── réception client ───────────────────────────────────────────────────
    async def receive_json(self, content, **kwargs):
        op = content.get("op")
        try:
            if op == "spawn":
                await self._op_spawn(content)
            elif op == "attach":
                await self._op_attach(content)
            elif op == "stdin":
                self._op_stdin(content)
            elif op == "resize":
                self.manager.resize(
                    str(content["pane_id"]),
                    int(content.get("cols", 120)),
                    int(content.get("rows", 32)),
                    owner_id=self.user.pk,
                )
            elif op == "kill":
                await self._op_kill(content)
            elif op == "set_visibility":
                await self._op_set_visibility(content)
            elif op == "set_live":
                await self._op_set_live(bool(content.get("live")))
            elif op == "panic":
                await self._op_panic()
            elif op == "chat_start":
                await self._op_chat_start(content)
            elif op == "chat_attach":
                await self._op_chat_attach(content)
            elif op == "chat_send":
                await self._op_chat_send(content)
            elif op == "chat_kill":
                await self._op_chat_kill(content)
            elif op == "chat_reset":
                await self._op_chat_reset(content)
            else:
                await self.send_json({"op": "error", "message": f"Opération inconnue : {op}"})
        except CapacityError as exc:
            # Sans trace serveur, un refus de capacité rend le pane orphelin
            # en « dead » sans aucune explication dans les logs.
            logger.warning(
                "capacité atteinte — %s refusé : pane=%s owner=%s : %s",
                op,
                content.get("pane_id"),
                getattr(self.user, "pk", None),
                exc,
            )
            await self.send_json({
                "op": "error", "pane_id": content.get("pane_id"),
                "message": str(exc), "code": "capacity",
            })
        except PaneError as exc:
            await self.send_json({"op": "error", "message": str(exc), "pane_id": content.get("pane_id")})
        except (KeyError, TypeError, ValueError) as exc:
            await self.send_json({"op": "error", "message": f"Message invalide : {exc}"})

    async def _op_spawn(self, content):
        record = await _load_pty_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        if runtime_id in self.manager.panes and self.manager.panes[runtime_id].status == "running":
            # Déjà vivant (autre onglet, F5…) : on bascule en attach.
            await self._attach_runtime(runtime_id)
            return
        if runtime_id in self.manager.panes:
            # Cadavre runtime d'une session précédente : on nettoie avant relance.
            await self.manager.kill(runtime_id, owner_id=self.user.pk)
        await _check_capacity(record)
        cmd = record.respawn_cmd() if content.get("continue") else record.cmd
        live, redactor = await _load_owner_context(self.user.pk)
        self.manager.live_by_owner.setdefault(self.user.pk, live)
        pane = await self.manager.spawn(
            cmd=cmd,
            cwd=record.effective_cwd(),
            cols=int(content.get("cols", 120)),
            rows=int(content.get("rows", 32)),
            owner_id=self.user.pk,
            pane_id=runtime_id,
            is_public=record.is_public,
            public_label=record.public_label,
            redactor=redactor,
        )
        await _stamp_running(record.pk)
        if record.is_public:
            await self.manager.notify_observer("panes_changed")
        await self._join(pane.group)
        await self.send_json({"op": "status", "pane_id": runtime_id, "status": "running"})

    async def _op_attach(self, content):
        # Reconnexion : shell.js ré-attache TOUS les panes via cette op. On
        # dispatche selon le type pour que les chats reçoivent leur replay.
        base = await _load_base_pane(content["pane_id"], self.user.pk)
        if base.kind == "headless":
            return await self._op_chat_attach(content)
        record = await _load_pty_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        if runtime_id not in self.manager.panes:
            # En base « running » mais absent du runtime = pane périmé
            # (restart serveur). On resynchronise et on laisse l'UI proposer
            # la relance (`--continue` pour claude).
            if record.status == Pane.Status.RUNNING:
                await _persist_status(record.pk, Pane.Status.DEAD)
            await self.send_json({"op": "status", "pane_id": runtime_id, "status": "dead"})
            return
        await self._attach_runtime(runtime_id)

    async def _attach_runtime(self, runtime_id: str):
        pane = self.manager.get_pane(runtime_id, owner_id=self.user.pk)
        await self._join(pane.group)
        replay = self.manager.replay(runtime_id, owner_id=self.user.pk)
        if replay:
            await self.send_json(
                {"op": "stdout", "pane_id": runtime_id, "data": base64.b64encode(replay).decode()}
            )
        await self.send_json({"op": "status", "pane_id": runtime_id, "status": pane.status})

    async def _op_kill(self, content):
        record = await _load_pty_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        if runtime_id in self.manager.panes:
            await self.manager.kill(runtime_id, owner_id=self.user.pk)
        await _persist_status(record.pk, Pane.Status.DEAD)
        await self.send_json({"op": "status", "pane_id": runtime_id, "status": "dead"})

    async def _op_set_visibility(self, content):
        record = await _load_base_pane(content["pane_id"], self.user.pk)
        public = bool(content.get("public"))
        await _persist_visibility(record.pk, public)
        runtime_id = str(record.pk)
        if runtime_id in self.manager.panes:
            _live, redactor = await _load_owner_context(self.user.pk)
            self.manager.set_visibility(
                runtime_id, public, owner_id=self.user.pk, public_label=record.public_label
            )
            self.manager.refresh_redactor(self.user.pk, redactor)
        if runtime_id in self.headless.sessions:
            _live, redactor = await _load_owner_context(self.user.pk)
            self.headless.set_visibility(
                runtime_id, public, owner_id=self.user.pk, public_label=record.public_label
            )
            self.headless.refresh_redactor(self.user.pk, redactor)
        await self.manager.notify_observer("panes_changed")
        await self.send_json({"op": "visibility", "pane_id": runtime_id, "public": public})

    async def _op_set_live(self, live: bool):
        await _persist_live(self.user.pk, live)
        self.manager.set_live(self.user.pk, live)
        if not live:
            self.headless.purge_public(self.user.pk)
        await self.manager.notify_observer("live" if live else "standby")
        await self.send_json({"op": "live", "live": live})

    async def _op_panic(self):
        """Bouton panique : coupe le direct ET repasse tout en privé,
        en base comme dans le runtime — une seule action, effet immédiat."""
        pks = await _panic_persist(self.user.pk)
        self.manager.set_live(self.user.pk, False)
        self.headless.purge_public(self.user.pk)
        for pk in pks:
            runtime_id = str(pk)
            if runtime_id in self.manager.panes:
                self.manager.set_visibility(runtime_id, False, owner_id=self.user.pk)
            if runtime_id in self.headless.sessions:
                self.headless.set_visibility(runtime_id, False, owner_id=self.user.pk)
        await self.manager.notify_observer("standby")
        await self.send_json({"op": "live", "live": False, "panic": True})

    async def _op_chat_start(self, content):
        record = await _load_headless_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        # Session déjà vivante (autre onglet, F5) : pas une nouvelle instance,
        # donc pas de consommation de capacité — sinon relancer l'UI ferait
        # échouer un pane qui tourne déjà.
        alive = (
            runtime_id in self.headless.sessions
            and self.headless.sessions[runtime_id].status == "running"
        )
        if not alive:
            await _check_capacity(record)
        live, redactor = await _load_owner_context(self.user.pk)
        self.manager.live_by_owner.setdefault(self.user.pk, live)
        resume = bool(content.get("resume"))
        session = await self.headless.start(
            runtime_id, owner_id=self.user.pk, cwd=record.effective_cwd(),
            is_public=record.is_public, public_label=record.public_label, redactor=redactor,
            resume=resume, resume_session_id=record.claude_session_id or None,
            model_id=getattr(record, "model_id", ""),
            system_prompt=getattr(record, "prompt_initial", "") or "",
        )
        await _stamp_running(record.pk)
        await self._join(session.group)
        await self.send_json({"op": "chat_status", "pane_id": runtime_id, "status": "running"})
        if record.is_public:
            await self.manager.notify_observer("panes_changed")

    async def _op_chat_attach(self, content):
        record = await _load_headless_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        await self._join(f"pane_{runtime_id}")
        # Replay depuis EventLog (durable : survit au restart serveur).
        events = await _replay_events(record.pk)
        await self.send_json({
            "op": "chat_replay", "pane_id": runtime_id,
            "events": [{"seq": seq, "event": norm} for seq, norm in events if norm],
        })
        alive = runtime_id in self.headless.sessions and self.headless.sessions[runtime_id].status == "running"
        if not alive and record.status == Pane.Status.RUNNING:
            await _persist_status(record.pk, Pane.Status.DEAD)
        await self.send_json({
            "op": "chat_status", "pane_id": runtime_id,
            "status": "running" if alive else "dead",
        })

    async def _op_chat_send(self, content):
        record = await _load_headless_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        text = (content.get("text") or "").strip()
        if not text:
            raise PaneError("Message vide.")
        if len(text) > 100_000:
            raise PaneError("Message trop long.")
        if runtime_id not in self.headless.sessions or self.headless.sessions[runtime_id].status != "running":
            live, redactor = await _load_owner_context(self.user.pk)
            self.manager.live_by_owner.setdefault(self.user.pk, live)
            # Un pane a une session connue ⇒ reprendre CETTE conversation
            # (continuité fidèle), sinon démarrage neuf.
            sid = record.claude_session_id or None
            await self.headless.start(
                runtime_id, owner_id=self.user.pk, cwd=record.effective_cwd(),
                is_public=record.is_public, public_label=record.public_label, redactor=redactor,
                resume=bool(sid), resume_session_id=sid,
                model_id=getattr(record, "model_id", ""),
                system_prompt=getattr(record, "prompt_initial", "") or "",
            )
            await _stamp_running(record.pk)
            await self._join(f"pane_{runtime_id}")
            await self.send_json({"op": "chat_status", "pane_id": runtime_id, "status": "running"})
        await self.headless.send(runtime_id, text, owner_id=self.user.pk)

    async def _op_chat_kill(self, content):
        record = await _load_headless_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        if runtime_id in self.headless.sessions:
            await self.headless.kill(runtime_id, owner_id=self.user.pk)
        await _persist_status(record.pk, Pane.Status.DEAD)
        await self.send_json({"op": "chat_status", "pane_id": runtime_id, "status": "dead"})

    async def _op_chat_reset(self, content):
        """Nouvelle conversation dans le même pane : coupe la session et oublie
        l'id Claude — le prochain envoi repart à neuf. Sert aussi d'échappatoire
        si une session stockée a expiré côté Claude Code."""
        record = await _load_headless_pane(content["pane_id"], self.user.pk)
        runtime_id = str(record.pk)
        if runtime_id in self.headless.sessions:
            await self.headless.kill(runtime_id, owner_id=self.user.pk)
        await _clear_session_id(record.pk)
        await _persist_status(record.pk, Pane.Status.DEAD)
        await self.send_json({"op": "chat_reset", "pane_id": runtime_id})

    def _op_stdin(self, content):
        try:
            data = base64.b64decode(content["data"], validate=True)
        except (binascii.Error, TypeError) as exc:
            raise PaneError("stdin non décodable (base64 attendu)") from exc
        if len(data) > MAX_STDIN_BYTES:
            raise PaneError("stdin trop volumineux")
        self.manager.write(str(content["pane_id"]), data, owner_id=self.user.pk)

    async def _join(self, group: str) -> None:
        if group not in self.joined_groups:
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined_groups.add(group)

    # ── événements du channel layer ────────────────────────────────────────
    async def pane_output(self, event):
        await self.send_json({"op": "stdout", "pane_id": event["pane_id"], "data": event["data"]})

    async def pane_status(self, event):
        await self.send_json({"op": "status", "pane_id": event["pane_id"], "status": event["status"]})

    async def chat_event(self, event):
        await self.send_json({
            "op": "chat_event", "pane_id": event["pane_id"],
            "seq": event["seq"], "event": event["event"],
        })

    async def chat_status(self, event):
        await self.send_json({"op": "chat_status", "pane_id": event["pane_id"], "status": event["status"]})
