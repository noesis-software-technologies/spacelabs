"""Portabilité du backend PTY : import sans dépendance Unix, sélection, handle."""
import sys

import pytest

from apps.runtime.services import pty_backend


def test_module_import_has_no_unix_only_toplevel_dependency():
    """pane_manager ne doit PAS importer ptyprocess/fcntl au chargement — sinon
    l'app crashe à l'import sur Windows (bug corrigé)."""
    import importlib

    src = importlib.util.find_spec("apps.runtime.services.pane_manager").origin
    head = "".join(open(src, encoding="utf-8").read().splitlines(keepends=True)[:45])
    assert "from ptyprocess import" not in head
    assert "import fcntl" not in head
    assert "import pty_backend" in head or "from . import pty_backend" in head


def test_is_windows_matches_platform():
    assert pty_backend.IS_WINDOWS == (sys.platform == "win32")


def test_spawn_selects_windows_backend(monkeypatch):
    """Sur Windows, spawn doit passer par pywinpty (et lever un message clair
    si absent) — sans jamais toucher ptyprocess."""
    monkeypatch.setattr(pty_backend, "IS_WINDOWS", True)
    with pytest.raises(pty_backend.PtyUnavailable) as exc:
        pty_backend.spawn(["cmd"], cwd=".", env={}, rows=24, cols=80)
    # message oriente vers pywinpty / WSL2
    assert "pywinpty" in str(exc.value) or "WSL2" in str(exc.value)


@pytest.mark.skipif(sys.platform == "win32", reason="chemin POSIX")
def test_posix_handle_roundtrip():
    """Le handle POSIX enveloppe ptyprocess : spawn → read/write → terminate."""
    h = pty_backend.spawn(["sh", "-c", "printf salut; sleep 5"], cwd="/tmp", env=dict(),
                          rows=24, cols=80)
    assert h.uses_fd is True and h.fd is not None and h.pid
    import time
    time.sleep(0.3)
    data = h.read_chunk(1024)
    assert b"salut" in data
    assert h.isalive()
    h.terminate(force=True)
    time.sleep(0.2)
    assert not h.isalive()
    h.close()
