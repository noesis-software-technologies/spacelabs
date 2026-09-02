#!/usr/bin/env python3
"""Vérifie la checklist bloquante d'une PR (Règle 2 : pas de merge sans critères d'acceptation cochés).

Les gabarits .github/PULL_REQUEST_TEMPLATE*.md contiennent des lignes ``- [ ] TOKEN: …``.
Ce script exige que chaque TOKEN du profil soit coché (``- [x] TOKEN:``), que la ligne
cochée ne contienne plus de placeholder ``<…>`` (ex. ``@<qa>``, ``<date>``) et, pour TICKET,
qu'un lien d'issue (``Closes #12``) figure dans la description.

Usage (CI) :  PR_BODY="…" check_pr_body.py --profile sub-feature
Usage (local): check_pr_body.py --profile integration --body-file body.md

Code de sortie : 0 = complet · 1 = incomplet (liste sur stdout + ``missing=…`` dans $GITHUB_OUTPUT).
Brouillon (``PR_DRAFT=true``) : les manquements sont listés en ``::notice::`` mais le code de sortie reste 0 —
une PR ouverte tôt en Draft (encouragé) n'est pas rouge tant qu'elle n'est pas « prête pour revue ».
"""

from __future__ import annotations

import argparse
import os
import re
import sys

PROFILES: dict[str, list[str]] = {
    "sub-feature": ["TICKET", "AC", "FLAG", "TESTS", "QA"],
    "integration": ["TICKET", "AC", "FLAG", "TESTS", "QA", "ROLLBACK", "ANALYTICS", "DOCS", "GTM"],
    "rollout": ["TICKET", "FLAG", "ROLLBACK", "ANALYTICS"],
    "hotfix": ["TICKET", "TESTS", "ROLLBACK"],
}

_BOX = re.compile(r"^\s*[-*]\s*\[(?P<state>[ xX])\]\s*(?P<token>[A-Z]{2,})\s*:(?P<rest>.*)$", re.M)
_ISSUE_LINK = re.compile(r"\b(?:closes|fixes|resolves|refs?)\s*:?\s*#\d+", re.I)
_PLACEHOLDER = re.compile(r"<[^>\n]{1,40}>")
_CODE_SPAN = re.compile(r"`[^`\n]*`")  # les notations `feature/<epic>` en code ne sont pas des placeholders


def checked_lines(body: str) -> dict[str, str]:
    """Retourne {TOKEN: reste de la ligne} pour chaque case cochée (dernière occurrence gagne)."""
    return {m.group("token").upper(): m.group("rest") for m in _BOX.finditer(body) if m.group("state").lower() == "x"}


def missing_tokens(body: str, profile: str) -> list[str]:
    """Liste des manquements pour le profil ; vide = checklist complète."""
    if profile not in PROFILES:
        raise ValueError(f"profil inconnu : {profile} (choix : {', '.join(PROFILES)})")
    checked = checked_lines(body or "")
    problems: list[str] = []
    for token in PROFILES[profile]:
        rest = checked.get(token)
        if rest is None:
            problems.append(token)
        elif _PLACEHOLDER.search(_CODE_SPAN.sub("", rest)):
            problems.append(f"{token}(placeholder non rempli)")
    if "TICKET" in PROFILES[profile] and "TICKET" in checked and not _ISSUE_LINK.search(body or ""):
        problems.append("TICKET(aucun 'Closes #n' dans la description)")
    return problems


def _write_output(missing: list[str]) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"missing={', '.join(missing)}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--body-file", help="fichier contenant la description ; défaut : $PR_BODY")
    args = parser.parse_args(argv)

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = os.environ.get("PR_BODY", "")

    missing = missing_tokens(body, args.profile)
    _write_output(missing)
    if missing and os.environ.get("PR_DRAFT", "").lower() == "true":
        print(
            f"::notice::brouillon — checklist {args.profile} incomplète ({', '.join(missing)}) : "
            "à cocher avant « Ready for review »"
        )
        return 0
    if missing:
        print(f"⛔ checklist {args.profile} incomplète : {', '.join(missing)}")
        print("   → coche les lignes '- [x] TOKEN:' correspondantes dans la description de la PR")
        return 1
    print(f"✅ checklist {args.profile} complète ({', '.join(PROFILES[args.profile])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
