"""PaneManager — le cœur du cockpit.

Spawne des process (Claude Code, shells) dans des pseudo-terminaux, pompe leur
sortie en asyncio et la publie sur le channel layer (groupe ``pane_{id}``) pour
un fan-out vers N abonnés. Conserve un ring buffer par pane pour rejouer
l'historique à la (re)connexion.

Invariants :
- lecture **non bloquante** : ``loop.add_reader`` sur le fd du PTY, jamais de
  thread bloqué ni de polling ;
- la sortie transite en **base64** (le flux ANSI peut couper l'UTF-8 en plein
  code-point — on ne décode jamais côté serveur) ;
- kill propre : SIGTERM → grâce → SIGKILL, ``add_reader`` retiré, fd fermé,
  zéro orphelin ;
- aucune info métier extraite du flux ANSI (CDC §8.4).

Sprint 1 : registre en mémoire (les modèles Workspace/Pane arrivent au
Sprint 2 ; ce module n'aura alors qu'à persister ce qu'il tient déjà).
"""
from __future__ import annotations

import asyncio
import base64
import dataclasses
import logging
import os
import shlex
import shutil
import threading
import uuid

from channels.layers import get_channel_layer
from django.conf import settings

from . import pty_backend
from .pty_backend import PtyUnavailable

logger = logging.getLogger("spacelabs.runtime")

READ_CHUNK = 65536
KILL_GRACE_SECONDS = 3.0
OBSERVER_GROUP = "observer_stream"  # flux public agrégé consommé par le SSE


def _noop_redactor(data: bytes) -> bytes:
    return data


class CommandNotAllowed(Exception):
    """Commande hors politique. Message destiné à l'utilisateur."""


def resolve_allowed_binary(requested: str) -> str:
    """Valide une commande et renvoie le chemin réel du binaire.

    RÈGLE UNIQUE du produit, partagée par le formulaire (validation à la
    saisie) et par le manager (contrôle au démarrage). Elle vivait en double,
    avec deux implémentations différentes : le formulaire comparait
    ``cmd.rsplit("/")[-1]``, donc « /tmp/evil/claude » passait la saisie et
    n'était refusé qu'au spawn — et une seule des deux copies avait été
    durcie. Deux règles pour une politique, c'est comme ça qu'un trou revient.

    Le nom doit être NU : la résolution passe par le PATH, comme un shell.
    """
    requested = (requested or "").strip()
    if not requested:
        raise CommandNotAllowed("Commande vide.")
    if os.sep in requested or (os.altsep and os.altsep in requested) or requested.startswith("~"):
        raise CommandNotAllowed(
            "Commande refusée : indique un nom de binaire nu "
            f"(« {os.path.basename(requested)} »), pas un chemin."
        )
    if requested not in settings.COCKPIT_ALLOWED_CMDS:
        allowed = ", ".join(settings.COCKPIT_ALLOWED_CMDS)
        raise CommandNotAllowed(
            f"« {requested} » n'est pas autorisé (liste blanche : {allowed})."
        )
    resolved = shutil.which(requested)
    if resolved is None:
        raise CommandNotAllowed(f"Binaire introuvable dans le PATH : {requested}")
    return resolved


class PaneError(Exception):
    """Erreur runtime remontée au consumer (message montrable à l'opérateur)."""


@dataclasses.dataclass
class Pane:
    id: str
    cmd: str
    argv: list[str]
    cwd: str
    proc: "pty_backend.PtyHandle"
    buffer: bytearray = dataclasses.field(default_factory=bytearray)
    status: str = "running"
    owner_id: int | None = None
    # ── Pipeline public (S3) — privé par défaut ────────────────────────────
    is_public: bool = False
    public_label: str = ""
    redact: "callable" = _noop_redactor
    buffer_public: bytearray = dataclasses.field(default_factory=bytearray)
    # Lecture Windows (pas de fd surveillable par la boucle) : thread + stop.
    reader_thread: object | None = None
    stop_reader: object | None = None

    @property
    def group(self) -> str:
        return f"pane_{self.id}"


class PaneManager:
    """Singleton par process ASGI. Toutes les méthodes s'exécutent dans la
    boucle d'événements du serveur (appelées depuis les consumers)."""

    _instance: "PaneManager | None" = None

    def __init__(self) -> None:
        self.panes: dict[str, Pane] = {}
        # Mode live par opérateur — live off ⇒ AUCUNE trame publique n'est
        # émise, quel que soit is_public des panes.
        self.live_by_owner: dict[int, bool] = {}

    # ── cycle de vie du singleton ──────────────────────────────────────────
    @classmethod
    def get(cls) -> "PaneManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._instance = None

    # ── API panes ──────────────────────────────────────────────────────────
    async def spawn(
        self,
        cmd: str | None = None,
        cwd: str | None = None,
        cols: int = 120,
        rows: int = 32,
        owner_id: int | None = None,
        pane_id: str | None = None,
        is_public: bool = False,
        public_label: str = "",
        redactor=None,
    ) -> Pane:
        # Garde-fou mémoire PAR PROPRIÉTAIRE. La décision de capacité est prise
        # en base (apps/runtime/capacity.py) : c'est la seule source vraie
        # cross-process. Ici on empêche seulement qu'un seul compte sature le
        # processus — avant S9 ce test était global et deux utilisateurs à 6
        # panes bloquaient tout le monde.
        mine = sum(1 for p in self.panes.values() if p.owner_id == owner_id)
        if mine >= settings.COCKPIT_MAX_PANES:
            raise PaneError(f"Limite de {settings.COCKPIT_MAX_PANES} panes atteinte.")

        cmd = (cmd or settings.COCKPIT_DEFAULT_CMD).strip()
        # posix=False sur Windows : ne pas manger les backslashes des chemins.
        argv = shlex.split(cmd, posix=(os.name == "posix"))
        if not argv:
            raise PaneError("Commande vide.")
        # [S17] La liste blanche comparait le SEUL nom de base : « ~/evil/claude »
        # et « ./sh » passaient, donc n'importe quel binaire portant un nom
        # autorisé s'exécutait. Ce n'est pas théorique — COCKPIT_LAN_TOKEN
        # expose ce chemin au réseau local.
        #
        # Règle : le nom doit être NU (aucun séparateur de chemin). La
        # résolution est laissée au PATH du système, comme un shell le ferait.
        # Un chemin absolu vers un binaire légitime n'est pas nécessaire ; s'il
        # le devient, il faudra une liste blanche de RÉPERTOIRES, pas un
        # assouplissement de celle-ci.
        try:
            argv[0] = resolve_allowed_binary(argv[0])
        except CommandNotAllowed as exc:
            raise PaneError(str(exc)) from exc

        cwd = os.path.expanduser(cwd or "~")
        if not os.path.isdir(cwd):
            raise PaneError(f"Répertoire introuvable : {cwd}")

        env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor")
        try:
            proc = pty_backend.spawn(argv, cwd=cwd, env=env, rows=rows, cols=cols)
        except PtyUnavailable as exc:
            raise PaneError(str(exc)) from exc
        except (FileNotFoundError, OSError) as exc:
            raise PaneError(f"Binaire introuvable : {argv[0]}") from exc

        pane = Pane(
            id=pane_id or uuid.uuid4().hex[:12],
            cmd=cmd, argv=argv, cwd=cwd, proc=proc, owner_id=owner_id,
            is_public=is_public, public_label=public_label,
            redact=redactor or _noop_redactor,
        )
        self.panes[pane.id] = pane

        loop = asyncio.get_running_loop()
        if proc.uses_fd:
            # POSIX : lecture non bloquante pilotée par la boucle (inchangé).
            loop.add_reader(proc.fd, self._on_readable, pane.id)
        else:
            # Windows : la boucle ne sait pas surveiller le PTY → thread pompe.
            self._start_thread_reader(pane, loop)
        logger.info("pane %s spawned pid=%s cmd=%r cwd=%s", pane.id, proc.pid, cmd, cwd)
        return pane

    def get_pane(self, pane_id: str, owner_id: int | None = None) -> Pane:
        pane = self.panes.get(pane_id)
        if pane is None:
            raise PaneError(f"Pane inconnu : {pane_id}")
        # [TENANCY] par user, appliquée aussi au registre mémoire : un pane
        # n'est adressable que par son propriétaire.
        if owner_id is not None and pane.owner_id is not None and pane.owner_id != owner_id:
            raise PaneError(f"Pane inconnu : {pane_id}")
        return pane

    def write(self, pane_id: str, data: bytes, owner_id: int | None = None) -> None:
        pane = self.get_pane(pane_id, owner_id)
        if pane.status != "running":
            raise PaneError("Pane terminé — impossible d'écrire.")
        pane.proc.write(data)

    def resize(self, pane_id: str, cols: int, rows: int, owner_id: int | None = None) -> None:
        pane = self.get_pane(pane_id, owner_id)
        if pane.status == "running":
            pane.proc.setwinsize(rows, cols)

    async def kill(self, pane_id: str, owner_id: int | None = None) -> None:
        pane = self.get_pane(pane_id, owner_id)
        await self._terminate(pane)
        self.panes.pop(pane_id, None)

    async def shutdown(self) -> None:
        for pane in list(self.panes.values()):
            await self._terminate(pane)
        self.panes.clear()

    def replay(self, pane_id: str, owner_id: int | None = None) -> bytes:
        return bytes(self.get_pane(pane_id, owner_id).buffer)

    # ── interne ────────────────────────────────────────────────────────────
    def _on_readable(self, pane_id: str) -> None:
        """Callback add_reader (POSIX) : lit un chunk et le publie. S'exécute
        dans la boucle — pas de blocage possible (le fd est signalé lisible)."""
        pane = self.panes.get(pane_id)
        if pane is None:
            return
        try:
            data = pane.proc.read_chunk(READ_CHUNK)
        except OSError:
            data = b""
        if not data:
            asyncio.get_running_loop().create_task(self._mark_dead(pane))
            return
        self._dispatch_read(pane_id, data)

    def _dispatch_read(self, pane_id: str, data: bytes) -> None:
        """Publie un chunk lu (chemin commun POSIX/Windows). Tourne dans la
        boucle."""
        pane = self.panes.get(pane_id)
        if pane is None:
            return
        self._append_buffer(pane, data)
        asyncio.get_running_loop().create_task(self._broadcast_output(pane, data))

    def _start_thread_reader(self, pane: "Pane", loop) -> None:
        """Windows : pompe les lectures bloquantes du PTY dans un thread et
        réinjecte chaque chunk dans la boucle (call_soon_threadsafe)."""
        pane.stop_reader = threading.Event()

        def _pump():
            while not pane.stop_reader.is_set():
                try:
                    data = pane.proc.read_chunk(READ_CHUNK)
                except OSError:
                    data = b""
                if not data:
                    loop.call_soon_threadsafe(
                        lambda: asyncio.ensure_future(self._mark_dead(pane))
                    )
                    return
                loop.call_soon_threadsafe(self._dispatch_read, pane.id, data)

        pane.reader_thread = threading.Thread(
            target=_pump, name=f"pty-read-{pane.id}", daemon=True
        )
        pane.reader_thread.start()

    def _append_buffer(self, pane: Pane, data: bytes) -> None:
        pane.buffer.extend(data)
        overflow = len(pane.buffer) - settings.COCKPIT_BUFFER_BYTES
        if overflow > 0:
            del pane.buffer[:overflow]

    def _public_flow_enabled(self, pane: Pane) -> bool:
        return bool(
            pane.is_public
            and pane.owner_id is not None
            and self.live_by_owner.get(pane.owner_id, False)
        )

    async def _broadcast_output(self, pane: Pane, data: bytes) -> None:
        layer = get_channel_layer()
        await layer.group_send(
            pane.group,
            {"type": "pane.output", "pane_id": pane.id, "data": base64.b64encode(data).decode()},
        )
        # ── Pipeline public : redaction serveur + gating live. Le buffer
        # public ne s'alimente QUE quand le flux est diffusable : passer un
        # pane en public ne révèle jamais son passé.
        if self._public_flow_enabled(pane):
            redacted = pane.redact(bytes(data))
            pane.buffer_public.extend(redacted)
            overflow = len(pane.buffer_public) - settings.COCKPIT_BUFFER_BYTES
            if overflow > 0:
                del pane.buffer_public[:overflow]
            await layer.group_send(
                OBSERVER_GROUP,
                {
                    "type": "observer.event",
                    "event": "stdout",
                    "pane_id": pane.id,
                    "data": base64.b64encode(redacted).decode(),
                },
            )

    async def notify_observer(self, event: str, **payload) -> None:
        layer = get_channel_layer()
        await layer.group_send(OBSERVER_GROUP, {"type": "observer.event", "event": event, **payload})

    def set_live(self, owner_id: int, live: bool) -> None:
        self.live_by_owner[owner_id] = live
        if not live:
            # Coupure du direct : on purge les buffers publics (rien à
            # rejouer aux spectateurs qui se reconnecteraient).
            for pane in self.panes.values():
                if pane.owner_id == owner_id:
                    pane.buffer_public.clear()

    def set_visibility(self, pane_id: str, public: bool, owner_id: int | None = None,
                       public_label: str | None = None) -> Pane:
        pane = self.get_pane(pane_id, owner_id)
        pane.is_public = public
        if public_label is not None:
            pane.public_label = public_label
        if not public:
            pane.buffer_public.clear()  # repasser en privé oublie tout
        return pane

    def refresh_redactor(self, owner_id: int, redactor) -> None:
        """Applique de nouvelles règles de masquage aux panes déjà vivants."""
        for pane in self.panes.values():
            if pane.owner_id == owner_id:
                pane.redact = redactor

    def replay_public(self, pane_id: str) -> bytes:
        """Replay pour l'observateur : buffer public expurgé UNIQUEMENT —
        jamais le buffer privé. Vide si pane privé ou live coupé."""
        pane = self.panes.get(pane_id)
        if pane is None or not self._public_flow_enabled(pane):
            return b""
        return bytes(pane.buffer_public)

    async def _mark_dead(self, pane: Pane) -> None:
        if pane.status == "dead":
            return
        pane.status = "dead"
        self._remove_reader(pane)
        logger.info("pane %s dead (pid=%s)", pane.id, pane.proc.pid)
        await self._persist_dead(pane)
        layer = get_channel_layer()
        await layer.group_send(
            pane.group, {"type": "pane.status", "pane_id": pane.id, "status": "dead"}
        )
        if self._public_flow_enabled(pane):
            await self.notify_observer("status", pane_id=pane.id, status="dead")

    @staticmethod
    async def _persist_dead(pane: Pane) -> None:
        """Persiste le statut si le pane est adossé à un enregistrement DB
        (id numérique = pk). Les panes purement runtime (tests) sont ignorés."""
        if not pane.id.isdigit():
            return
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _update():
            from apps.workspaces.models import Pane as PaneRecord

            PaneRecord.objects.filter(pk=int(pane.id)).update(status="dead")

        await _update()

    def _remove_reader(self, pane: Pane) -> None:
        if pane.proc.uses_fd:
            try:
                asyncio.get_running_loop().remove_reader(pane.proc.fd)
            except (ValueError, OSError):  # fd déjà fermé
                pass
        elif pane.stop_reader is not None:
            pane.stop_reader.set()  # Windows : arrête le thread lecteur

    async def _terminate(self, pane: Pane) -> None:
        self._remove_reader(pane)
        proc = pane.proc
        if proc.isalive():
            try:
                proc.terminate(force=False)
            except OSError:
                pass
            deadline = asyncio.get_running_loop().time() + KILL_GRACE_SECONDS
            while proc.isalive() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.05)
            if proc.isalive():
                try:
                    proc.terminate(force=True)
                except OSError:
                    pass
                while proc.isalive():
                    await asyncio.sleep(0.05)
        proc.close()
        pane.status = "dead"
        logger.info("pane %s terminated", pane.id)
