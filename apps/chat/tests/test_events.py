"""Parsing / normalisation / redaction des événements stream-json."""
from apps.chat.events import normalize, parse_line, redact_event, user_event
from apps.observer.redaction import compile_redactor


def test_parse_line_handles_blank_and_garbage():
    assert parse_line("") is None
    assert parse_line("   ") is None
    assert parse_line("pas du json") is None
    assert parse_line('{"type":"result"}') == {"type": "result"}


def test_normalize_system():
    ev = normalize({"type": "system", "subtype": "init", "model": "claude-x",
                    "tools": ["Bash", "Read"]})
    assert ev == {"kind": "system", "model": "claude-x", "tools_count": 2}


def test_normalize_assistant_text_and_tool_use():
    ev = normalize({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "Bonjour"},
        {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "ls"}},
    ]}})
    assert ev["kind"] == "assistant"
    assert ev["blocks"][0] == {"type": "text", "text": "Bonjour"}
    assert ev["blocks"][1]["name"] == "Bash"
    assert ev["blocks"][1]["input"] == {"command": "ls"}


def test_normalize_tool_result():
    ev = normalize({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"},
    ]}})
    assert ev == {"kind": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}


def test_normalize_result_extracts_cost_and_duration():
    ev = normalize({"type": "result", "subtype": "success", "is_error": False,
                    "duration_ms": 1500, "total_cost_usd": 0.02, "num_turns": 3})
    assert ev["kind"] == "result"
    assert ev["duration_ms"] == 1500
    assert ev["cost_usd"] == 0.02
    assert ev["num_turns"] == 3


def test_normalize_empty_assistant_returns_none():
    assert normalize({"type": "assistant", "message": {"content": []}}) is None


def test_redact_assistant_text_and_tool_input():
    redact = compile_redactor([("SECRET42", "•••", False)])
    ev = {"kind": "assistant", "blocks": [
        {"type": "text", "text": "voici SECRET42"},
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "echo SECRET42"}},
    ]}
    out = redact_event(ev, redact)
    assert out["blocks"][0]["text"] == "voici •••"
    # l'input reste un objet JSON, secret masqué dedans
    assert "SECRET42" not in str(out["blocks"][1]["input"])
    assert "•••" in str(out["blocks"][1]["input"])


def test_redact_user_and_tool_result():
    redact = compile_redactor([("motdepasse", "[X]", False)])
    assert redact_event(user_event("mon motdepasse"), redact) == {"kind": "user", "text": "mon [X]"}
    tr = {"kind": "tool_result", "tool_use_id": "t", "content": "motdepasse=1"}
    assert redact_event(tr, redact)["content"] == "[X]=1"


def test_redact_leaves_result_untouched():
    redact = compile_redactor([("x", "y", False)])
    ev = {"kind": "result", "subtype": "success", "duration_ms": 1, "cost_usd": 0, "num_turns": 1}
    assert redact_event(ev, redact) == ev
