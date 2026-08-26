"""Compilation des règles de masquage en une fonction bytes → bytes.

S'applique sur le flux ANSI brut AVANT toute publication publique.
Limite documentée (CDC §8) : un motif coupé à cheval sur deux chunks TCP
peut partiellement échapper au filet — d'où la règle produit « confidentiel
⇒ pane privé ». La redaction n'est jamais présentée comme une garantie.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

logger = logging.getLogger("spacelabs.observer")

Redactor = Callable[[bytes], bytes]


def compile_redactor(rules) -> Redactor:
    """``rules`` : itérable de (pattern, replacement, is_regex)."""
    literals: list[tuple[bytes, bytes]] = []
    regexes: list[tuple[re.Pattern[bytes], bytes]] = []
    for pattern, replacement, is_regex in rules:
        if not pattern:
            continue
        if is_regex:
            try:
                regexes.append((re.compile(pattern.encode()), replacement.encode()))
            except re.error as exc:
                logger.warning("règle regex ignorée (%r) : %s", pattern, exc)
        else:
            literals.append((pattern.encode(), replacement.encode()))

    def redact(data: bytes) -> bytes:
        for pat, repl in literals:
            data = data.replace(pat, repl)
        for rx, repl in regexes:
            data = rx.sub(repl, data)
        return data

    return redact


def redactor_for_rules_qs(qs) -> Redactor:
    return compile_redactor(
        qs.filter(is_active=True).values_list("pattern", "replacement", "is_regex")
    )
