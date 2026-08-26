"""Abstraction PTY multiplateforme (portabilité Windows).

Le cœur du cockpit spawne des process dans un pseudo-terminal. Le modèle diffère
radicalement selon l'OS :

- **POSIX** : ``ptyprocess`` — un fd surveillé par ``loop.add_reader`` (lecture
  non bloquante dans la boucle). Comportement inchangé depuis le Sprint 1.
- **Windows** : ``pywinpty`` (ConPTY) — pas de fd surveillable par la boucle
  asyncio ; la lecture est bloquante et sera pompée par un thread côté manager.

L'import de la lib spécifique est **paresseux** (dans ``spawn``) : importer ce
module ne dépend d'AUCUNE lib Unix-only (fini le ``import fcntl`` au chargement
via ptyprocess). L'application démarre donc sur Windows même sans backend PTY —
seuls les panes terminal exigent la lib de la plateforme.
"""
from __future__ import annotations

import os
import sys

IS_WINDOWS = sys.platform == "win32"


class PtyUnavailable(RuntimeError):
    """Aucun backend PTY utilisable sur cette plateforme."""


class PtyHandle:
    """Interface uniforme exposée au PaneManager."""

    uses_fd: bool = True   # True => fd surveillable (add_reader) ; False => thread
    fd: int | None = None
    pid: int | None = None

    def read_chunk(self, size: int) -> bytes:
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def setwinsize(self, rows: int, cols: int) -> None:
        raise NotImplementedError

    def isalive(self) -> bool:
        raise NotImplementedError

    def terminate(self, force: bool = False) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class _PosixHandle(PtyHandle):
    """ptyprocess : fd + os.read/os.write + signaux. Sémantique d'origine."""

    uses_fd = True

    def __init__(self, proc):
        self._proc = proc
        self.fd = proc.fd
        self.pid = proc.pid

    def read_chunk(self, size):
        return os.read(self.fd, size)

    def write(self, data):
        os.write(self.fd, data)

    def setwinsize(self, rows, cols):
        self._proc.setwinsize(rows, cols)

    def isalive(self):
        return self._proc.isalive()

    def terminate(self, force=False):
        import signal

        # SIGKILL n'existe pas partout ; repli sur SIGTERM le cas échéant.
        sig = getattr(signal, "SIGKILL", signal.SIGTERM) if force else signal.SIGTERM
        self._proc.kill(sig)

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


class _WindowsHandle(PtyHandle):
    """pywinpty (ConPTY) : lecture bloquante (pompée par un thread), écriture et
    dimensionnement par méthodes, terminaison sans signaux POSIX.

    NON vérifié dans l'environnement de build (Linux) — voir README/AUDIT."""

    uses_fd = False

    def __init__(self, proc):
        self._proc = proc
        self.fd = None
        self.pid = getattr(proc, "pid", None)

    def read_chunk(self, size):
        try:
            data = self._proc.read(size)
        except EOFError:
            return b""
        if not data:
            return b""
        return data.encode("utf-8", "replace") if isinstance(data, str) else data

    def write(self, data):
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8", "replace")
        self._proc.write(data)

    def setwinsize(self, rows, cols):
        self._proc.setwinsize(rows, cols)

    def isalive(self):
        return self._proc.isalive()

    def terminate(self, force=False):
        self._proc.terminate(force)

    def close(self):
        try:
            self._proc.close()
        except Exception:  # noqa: BLE001 — nettoyage best-effort
            pass


def spawn(argv, cwd, env, rows, cols) -> PtyHandle:
    """Lance ``argv`` dans un PTY et renvoie un handle uniforme. L'import de la
    lib de plateforme est fait ici (paresseux), jamais au chargement du module."""
    if IS_WINDOWS:
        try:
            from winpty import PtyProcess as WinPtyProcess
        except ImportError as exc:
            raise PtyUnavailable(
                "Terminaux Windows : installe pywinpty (pip install pywinpty), "
                "ou lance le cockpit sous WSL2 (recommandé)."
            ) from exc
        proc = WinPtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))
        return _WindowsHandle(proc)

    try:
        from ptyprocess import PtyProcess
    except ImportError as exc:
        raise PtyUnavailable("Terminaux POSIX : ptyprocess requis.") from exc
    proc = PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))
    return _PosixHandle(proc)
