"""Événements stream-json : parsing, normalisation, redaction.

Le flux `claude -p --output-format stream-json` est une suite de lignes JSON.
On normalise chaque ligne en un événement compact et stable, indépendant des
détails d'API — c'est CE format que le client rend et que la redaction
traite. La persistance (EventLog), elle, garde la ligne brute (intégrale).
"""
from __future__ import annotations

import json
from typing import Any, Callable


def parse_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def normalize(raw: dict) -> dict | None:
    """Événement brut Claude → événement d'affichage compact.

    Formes produites :
      {kind:"system", model, tools_count}
      {kind:"assistant", blocks:[{type:"text",text} | {type:"tool_use",id,name,input}]}
      {kind:"tool_result", tool_use_id, content}
      {kind:"result", subtype, duration_ms, cost_usd, num_turns}
    (le tour humain est synthétisé ailleurs en {kind:"user", text}).
    """
    etype = raw.get("type")
    if etype == "system":
        return {
            "kind": "system",
            "model": raw.get("model", ""),
            "tools_count": len(raw.get("tools") or []),
        }
    if etype == "assistant":
        blocks = []
        for block in (raw.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                blocks.append({"type": "text", "text": block.get("text", "")})
            elif block.get("type") == "tool_use":
                blocks.append({
                    "type": "tool_use",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                })
        if not blocks:
            return None
        return {"kind": "assistant", "blocks": blocks}
    if etype == "user":
        for block in (raw.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                content = block.get("content", "")
                if isinstance(content, list):  # certains formats renvoient des blocs
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict)
                    )
                return {
                    "kind": "tool_result",
                    "tool_use_id": block.get("tool_use_id", ""),
                    "content": content,
                }
        return None
    if etype == "result":
        return {
            "kind": "result",
            "subtype": raw.get("subtype", ""),
            "is_error": bool(raw.get("is_error")),
            "duration_ms": raw.get("duration_ms", 0),
            "cost_usd": raw.get("total_cost_usd", 0),
            "num_turns": raw.get("num_turns", 0),
        }
    return None


def user_event(text: str) -> dict:
    """Événement synthétique du tour humain (Claude ne le renvoie pas)."""
    return {"kind": "user", "text": text}


def _redact_str(value: str, redact: Callable[[bytes], bytes]) -> str:
    return redact(value.encode()).decode(errors="replace")


def redact_event(event: dict, redact: Callable[[bytes], bytes]) -> dict:
    """Applique le masquage (bytes→bytes, le MÊME que pour le PTY) aux seuls
    champs textuels d'un événement normalisé. Renvoie une copie."""
    kind = event.get("kind")
    if kind == "user":
        return {"kind": "user", "text": _redact_str(event.get("text", ""), redact)}
    if kind == "assistant":
        blocks = []
        for block in event.get("blocks", []):
            if block.get("type") == "text":
                blocks.append({"type": "text", "text": _redact_str(block.get("text", ""), redact)})
            else:  # tool_use : masquer l'input sérialisé
                raw_input = json.dumps(block.get("input", {}), ensure_ascii=False)
                safe_input = _redact_str(raw_input, redact)
                try:
                    parsed: Any = json.loads(safe_input)
                except json.JSONDecodeError:
                    parsed = {"_": safe_input}
                blocks.append({
                    "type": "tool_use", "id": block.get("id", ""),
                    "name": block.get("name", ""), "input": parsed,
                })
        return {"kind": "assistant", "blocks": blocks}
    if kind == "tool_result":
        return {
            "kind": "tool_result",
            "tool_use_id": event.get("tool_use_id", ""),
            "content": _redact_str(str(event.get("content", "")), redact),
        }
    # system / result : pas de contenu sensible libre
    return dict(event)
