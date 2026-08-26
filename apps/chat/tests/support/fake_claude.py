#!/usr/bin/env python3
"""Faux `claude -p --output-format stream-json` pour les tests/smoke.

Reproduit le protocole stream-json bidirectionnel de Claude Code SANS le
binaire réel : émet un événement `system/init`, puis pour CHAQUE tour lu sur
stdin (une ligne JSON `{"type":"user",...text...}`), produit une séquence
assistant(text) → assistant(tool_use) → user(tool_result) → assistant(text)
→ result(coût/durée), le tout en JSON-lignes flushées. EOF stdin ⇒ sortie.

Le texte du prompt est renvoyé verbatim dans la sortie : ça permet aux tests
de planter un secret dans le prompt et de vérifier sa redaction publique.
"""
import json
import os
import sys
import uuid

SESSION = "sess-" + uuid.uuid4().hex[:8]

# Test infra : si FAKE_CLAUDE_ARGV_LOG est défini, on journalise les args reçus
# (une ligne par invocation) — permet aux smokes de prouver que --resume <id>
# a bien été transmis au binaire par le cockpit.
_argv_log = os.environ.get("FAKE_CLAUDE_ARGV_LOG")
if _argv_log:
    try:
        with open(_argv_log, "a", encoding="utf-8") as _fh:
            _fh.write(" ".join(sys.argv[1:]) + "\n")
    except OSError:
        pass


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    emit({
        "type": "system", "subtype": "init", "session_id": SESSION,
        "model": "claude-fake-1", "tools": ["Bash", "Read", "Edit"], "cwd": "/tmp",
    })
    turn = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Extraire le texte du tour utilisateur
        text = ""
        content = (msg.get("message") or {}).get("content") or []
        if isinstance(content, str):
            text = content
        else:
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
        turn += 1
        tool_id = f"toolu_{turn}"
        emit({"type": "assistant", "session_id": SESSION, "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": f"Je traite : {text}"}]}})
        emit({"type": "assistant", "session_id": SESSION, "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": tool_id, "name": "Bash",
                          "input": {"command": f"echo {text}"}}]}})
        emit({"type": "user", "session_id": SESSION, "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_id,
                          "content": f"{text}"}]}})
        emit({"type": "assistant", "session_id": SESSION, "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": f"Terminé : {text}"}]}})
        emit({"type": "result", "subtype": "success", "is_error": False,
              "duration_ms": 1234, "num_turns": turn, "session_id": SESSION,
              "result": f"Terminé : {text}", "total_cost_usd": 0.0123,
              "usage": {"input_tokens": 100, "output_tokens": 50}})


if __name__ == "__main__":
    main()
