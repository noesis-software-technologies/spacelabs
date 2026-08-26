"""Reprise headless fidèle (--resume <session_id>)."""
from pathlib import Path

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.runtime.routing import websocket_urlpatterns
from apps.runtime.services.headless_manager import HeadlessManager
from apps.runtime.services.pane_manager import PaneManager
from apps.workspaces.models import HeadlessPane, Pane, Workspace

FAKE = str(Path(__file__).parent.parent.parent / "chat" / "tests" / "support" / "fake_claude.py")

pytestmark_async = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


# ── _build_argv (pur, sans process) ───────────────────────────────────────
def test_build_argv_resume_by_id(settings):
    settings.COCKPIT_CLAUDE_BIN = "claude"
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = ["-p", "--output-format", "stream-json"]
    argv = HeadlessManager._build_argv(resume=True, resume_session_id="sess-abc")
    assert "--resume" in argv
    assert argv[argv.index("--resume") + 1] == "sess-abc"
    assert "--continue" not in argv
    # le binaire reste en tête
    assert argv[0] == "claude"


def test_build_argv_continue_when_no_id(settings):
    settings.COCKPIT_CLAUDE_BIN = "claude"
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = ["-p"]
    argv = HeadlessManager._build_argv(resume=True, resume_session_id=None)
    assert "--continue" in argv
    assert "--resume" not in argv


def test_build_argv_fresh(settings):
    settings.COCKPIT_CLAUDE_BIN = "claude"
    settings.COCKPIT_CLAUDE_HEADLESS_ARGS = ["-p"]
    argv = HeadlessManager._build_argv(resume=False, resume_session_id="sess-x")
    assert "--resume" not in argv and "--continue" not in argv


# ── Bout-en-bout contre le faux binaire ───────────────────────────────────
class TestResumeE2E:
    pytestmark = pytestmark_async

    @pytest.fixture(autouse=True)
    def _fake(self, settings):
        settings.COCKPIT_CLAUDE_BIN = FAKE
        settings.COCKPIT_CLAUDE_HEADLESS_ARGS = []
        HeadlessManager.reset_for_tests()
        PaneManager.reset_for_tests()
        yield
        HeadlessManager.reset_for_tests()
        PaneManager.reset_for_tests()

    async def _connect(self, user):
        c = WebsocketCommunicator(URLRouter(websocket_urlpatterns), "/ws/cockpit/")
        c.scope["user"] = user
        ok, _ = await c.connect()
        assert ok
        return c

    async def _pane(self, session_id=""):
        user = await get_user_model().objects.acreate(username="pilote")
        ws = await Workspace.objects.acreate(owner=user, name="A", cwd="/tmp")
        pane = await HeadlessPane.objects.acreate(workspace=ws, claude_session_id=session_id)
        return user, pane

    async def _drain_until(self, c, pred, budget=40):
        for _ in range(budget):
            msg = await c.receive_json_from(timeout=6)
            if pred(msg):
                return msg
        raise AssertionError("condition jamais atteinte")

    async def test_session_id_persisted_on_init(self):
        """Après un échange, l'id de session Claude (émis à l'init) est stocké."""
        user, pane = await self._pane()
        c = await self._connect(user)
        await c.send_json_to({"op": "chat_send", "pane_id": pane.pk, "text": "salut"})
        await self._drain_until(
            c, lambda m: m.get("op") == "chat_event" and m["event"].get("kind") == "result"
        )
        await pane.arefresh_from_db()
        assert pane.claude_session_id.startswith("sess-")
        await c.send_json_to({"op": "chat_kill", "pane_id": pane.pk})
        await c.disconnect()

    async def test_chat_start_resume_passes_stored_id(self, monkeypatch):
        user, pane = await self._pane(session_id="sess-STORED")
        captured = {}
        real = HeadlessManager.start

        async def spy(self, *a, **k):
            captured["resume"] = k.get("resume")
            captured["sid"] = k.get("resume_session_id")
            return await real(self, *a, **k)

        monkeypatch.setattr(HeadlessManager, "start", spy)
        c = await self._connect(user)
        await c.send_json_to({"op": "chat_start", "pane_id": pane.pk, "resume": True})
        await self._drain_until(c, lambda m: m.get("op") == "chat_status" and m["status"] == "running")
        assert captured["resume"] is True
        assert captured["sid"] == "sess-STORED"
        await c.send_json_to({"op": "chat_kill", "pane_id": pane.pk})
        await c.disconnect()

    async def test_chat_send_continues_known_conversation(self, monkeypatch):
        """Envoyer dans un pane à session connue reprend CETTE conversation."""
        user, pane = await self._pane(session_id="sess-KNOWN")
        captured = {}
        real = HeadlessManager.start

        async def spy(self, *a, **k):
            captured["sid"] = k.get("resume_session_id")
            return await real(self, *a, **k)

        monkeypatch.setattr(HeadlessManager, "start", spy)
        c = await self._connect(user)
        await c.send_json_to({"op": "chat_send", "pane_id": pane.pk, "text": "suite"})
        await self._drain_until(c, lambda m: m.get("op") == "chat_status" and m["status"] == "running")
        assert captured["sid"] == "sess-KNOWN"
        await c.send_json_to({"op": "chat_kill", "pane_id": pane.pk})
        await c.disconnect()

    async def test_chat_reset_clears_session_id(self):
        user, pane = await self._pane(session_id="sess-OLD")
        c = await self._connect(user)
        await c.send_json_to({"op": "chat_reset", "pane_id": pane.pk})
        await self._drain_until(c, lambda m: m.get("op") == "chat_reset")
        await pane.arefresh_from_db()
        assert pane.claude_session_id == ""
        assert pane.status == Pane.Status.DEAD
        await c.disconnect()
