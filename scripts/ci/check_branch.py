#!/usr/bin/env python3
"""Convention de branches du harnais (hiérarchie Épic → sous-tâches → intégration → tronc).

    sub-feature/<epic>/<task>   →  feature/<epic>      (sub-team)
    feature/<epic>              →  main                (intégration, Main Dev Team)
    release/<epic>-<palier>     →  main                (palier de rollout d'un flag)
    hotfix/<slug>               →  main                (correctif urgent)
    dependabot/**               →  main                (exempté)

Slugs en kebab-case : [a-z0-9]+(-[a-z0-9]+)*. Le tronc est ``main`` (variable DEFAULT_BRANCH).

Usage : check_branch.py --head <branche> --base <branche>      → code 0/1 + message
        check_branch.py --head <branche> --expected-base       → imprime la base attendue
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"

_TRUNK = os.environ.get("DEFAULT_BRANCH", "main")

RULES: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str]]] = [
    (re.compile(rf"^sub-feature/(?P<epic>{SLUG})/(?P<task>{SLUG})$"), lambda m: f"feature/{m['epic']}"),
    (re.compile(rf"^feature/(?P<epic>{SLUG})$"), lambda m: _TRUNK),
    (re.compile(rf"^release/{SLUG}$"), lambda m: _TRUNK),
    (re.compile(rf"^hotfix/{SLUG}$"), lambda m: _TRUNK),
    (re.compile(r"^dependabot/.+$"), lambda m: _TRUNK),
]


def expected_base(head: str) -> str | None:
    """Base attendue pour une branche, ou None si la branche est hors convention."""
    for pattern, base_for in RULES:
        m = pattern.match(head)
        if m:
            return base_for(m)
    return None


def check(head: str, base: str) -> tuple[bool, str]:
    exp = expected_base(head)
    if exp is None:
        return False, (
            f"branche '{head}' hors convention. Attendu : sub-feature/<epic>/<task>, feature/<epic>, "
            f"release/<epic>-<palier> ou hotfix/<slug> (kebab-case)."
        )
    if exp != base:
        return False, f"'{head}' doit cibler '{exp}', pas '{base}'."
    return True, f"'{head}' → '{base}' : convention respectée."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base")
    parser.add_argument("--expected-base", action="store_true", help="imprime la base attendue et sort")
    args = parser.parse_args(argv)

    if args.expected_base:
        exp = expected_base(args.head)
        if exp is None:
            print(f"⛔ branche '{args.head}' hors convention", file=sys.stderr)
            return 1
        print(exp)
        return 0
    if not args.base:
        parser.error("--base requis (ou --expected-base)")
    ok, msg = check(args.head, args.base)
    print(("✅ " if ok else "⛔ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
