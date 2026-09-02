#!/usr/bin/env python3
"""Go / No-Go de lancement d'un épic — le tableau de bord automatique de ProdOps.

Agrège ce que la réunion Go/No-Go vérifie à la main (PM : AC · QA : zéro bug S1/S2 · Tech lead : rollback ·
PMM : GTM · Analyste : événements · CTO : tier 1) à partir de GitHub, et rend un verdict par **tier de
lancement** :

  tier 1  lancement majeur  : tout + sign-off exécutif (label ``exec-approved`` sur la PR d'intégration)
  tier 2  release standard  : tout (checklist complète, dont GTM = notes de release PMM)
  tier 3  mineur / correctif: idem tier 2 (GTM = entrée CHANGELOG) — la ligne ``GTM:`` reste exigée

Entrée : un JSON assemblé par ``scripts/gh/32-go-no-go.sh`` (ou un fixture de test) :
  epic, tier, slug, flag, pod, sub_issues, open_prs, integration_pr, bugs, registry_head
Sortie : rapport Markdown sur stdout · code 0 = GO · 1 = NO-GO · 2 = données invalides.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_pr_body import missing_tokens  # noqa: E402

BLOCKING_SEVERITIES = ("S1", "S2")
GREEN = {"SUCCESS", "NEUTRAL", "SKIPPED"}
RED = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "ERROR", "STARTUP_FAILURE"}
_SEV_LABEL = re.compile(r"^severity:(S[1-4])$", re.I)
_SEV_BODY = re.compile(r"###\s*Sévérité\s*\n+\s*(S[1-4])", re.I)


@dataclass
class Item:
    label: str
    ok: bool | None  # True = ✅, False = ⛔, None = ⏳ (en attente, non bloquant)
    detail: str = ""
    blocking: bool = True

    @property
    def icon(self) -> str:
        return "✅" if self.ok else ("⏳" if self.ok is None else "⛔")


def _labels(obj: dict | None) -> list[str]:
    if not obj:
        return []
    return [lab["name"] if isinstance(lab, dict) else str(lab) for lab in obj.get("labels", [])]


def tier_of(epic: dict, fallback: int = 2) -> int:
    """Tier lu dans les labels (``tier:N``) puis dans le corps du formulaire (``### Tier de lancement``)."""
    for lab in _labels(epic):
        m = re.match(r"^tier:([123])$", lab)
        if m:
            return int(m.group(1))
    m = re.search(r"###\s*Tier de lancement\s*\n+\s*([123])", epic.get("body") or "")
    return int(m.group(1)) if m else fallback


def bug_severity(bug: dict) -> str | None:
    for lab in _labels(bug):
        m = _SEV_LABEL.match(lab)
        if m:
            return m.group(1).upper()
    m = _SEV_BODY.search(bug.get("body") or "")
    return m.group(1).upper() if m else None


def bug_is_linked(bug: dict, epic_number: int, pod: str, flag: str) -> bool:
    body = (bug.get("body") or "") + " " + (bug.get("title") or "")
    if re.search(rf"(?<![\w/])#{epic_number}\b", body):
        return True
    if flag and flag in body:
        return True
    return f"pod:{pod}" in _labels(bug)


def evaluate(data: dict) -> tuple[list[Item], int, bool]:
    epic = data["epic"]
    number = int(epic["number"])
    slug, flag, pod = data["slug"], data.get("flag", ""), data.get("pod", "")
    tier = int(data.get("tier") or tier_of(epic))
    pr = data.get("integration_pr")
    items: list[Item] = []

    # 0. Cadrage
    items.append(Item("Épic approuvé par le leadership produit (`epic:approved`)", "epic:approved" in _labels(epic)))

    # 1. Sous-tâches
    subs = [s for s in data.get("sub_issues", []) if "sub-task" in _labels(s) or not _labels(s)]
    open_subs = [s for s in subs if str(s.get("state", "")).lower() == "open"]
    items.append(
        Item(
            f"Sous-tâches fermées ({len(subs) - len(open_subs)}/{len(subs)})",
            not open_subs if subs else None,
            ", ".join(f"#{s['number']}" for s in open_subs) if open_subs else ("" if subs else "aucune rattachée"),
            blocking=bool(subs),
        )
    )

    # 2. PR sub-feature encore ouvertes
    prefix = f"sub-feature/{slug}/"
    open_sub_prs = [p for p in data.get("open_prs", []) if str(p.get("headRefName", "")).startswith(prefix)]
    items.append(
        Item(
            f"Aucune PR `sub-feature/{slug}/*` ouverte",
            not open_sub_prs,
            ", ".join(f"#{p['number']}" for p in open_sub_prs),
        )
    )

    # 3. PR d'intégration
    if not pr:
        items.append(Item(f"PR d'intégration `feature/{slug}` → main ouverte", False, "25-open-pr.sh depuis feature/*"))
    else:
        items.append(Item(f"PR d'intégration #{pr['number']} prête (pas un brouillon)", not pr.get("isDraft", False)))
        missing = missing_tokens(pr.get("body") or "", "integration")
        items.append(
            Item("Checklist bloquante complète (AC · QA · ROLLBACK · ANALYTICS · GTM)", not missing, ", ".join(missing))
        )
        checks = pr.get("statusCheckRollup") or []
        red = [c for c in checks if str(c.get("conclusion") or "").upper() in RED]
        pending = [c for c in checks if str(c.get("conclusion") or "").upper() not in GREEN | RED]
        names = lambda cs: ", ".join(str(c.get("name") or c.get("context") or "?") for c in cs)  # noqa: E731
        if red:
            items.append(Item("Checks CI verts sur la PR d'intégration", False, names(red)))
        elif pending or not checks:
            items.append(Item("Checks CI verts sur la PR d'intégration", None, names(pending) or "aucun check remonté"))
        else:
            items.append(Item("Checks CI verts sur la PR d'intégration", True))
        decision = str(pr.get("reviewDecision") or "").upper()
        items.append(
            Item(
                "Revues de code approuvées (code owners, 2 approbations)",
                True if decision == "APPROVED" else (False if decision == "CHANGES_REQUESTED" else None),
                decision.lower() or "en attente",
            )
        )

    # 4. Bugs bloquants
    bugs = [
        b
        for b in data.get("bugs", [])
        if bug_severity(b) in BLOCKING_SEVERITIES and bug_is_linked(b, number, pod, flag)
    ]
    items.append(
        Item(
            "Zéro bug S1/S2 ouvert lié à l'épic (QA)",
            not bugs,
            ", ".join(f"#{b['number']} ({bug_severity(b)})" for b in bugs),
        )
    )

    # 5. Flag déclaré à off sur la branche d'intégration
    entry = next((f for f in data.get("registry_head", []) if f.get("name") == flag), None)
    state = str(entry.get("state")).lower() if entry else None
    items.append(
        Item(
            f"Flag `{flag}` déclaré à `off` sur `feature/{slug}`",
            bool(entry) and state in ("off", "false"),
            "" if entry else "absent du registre — Règle 3",
        )
    )

    # 6. Sign-off exécutif (tier 1)
    if tier == 1:
        items.append(
            Item(
                "Sign-off exécutif (label `exec-approved` sur la PR d'intégration — CTO / CPO)",
                bool(pr) and "exec-approved" in _labels(pr),
                "lancement majeur : `EXEC_APPROVERS` posent le label",
            )
        )

    # 7. Go PO — informatif : c'est l'étape SUIVANTE
    if pr:
        items.append(
            Item("Go PO (`po-approved`) — étape suivante", "po-approved" in _labels(pr) or None, blocking=False)
        )

    go = all(i.ok for i in items if i.blocking)
    return items, tier, go


TIER_TEXT = {
    1: "Tier 1 — lancement majeur : CPO/CTO, GTM complet, presse, formation ventes",
    2: "Tier 2 — release standard : géré dans le pod, notes de release PMM",
    3: "Tier 3 — mineur / correctif : EM + QA, entrée CHANGELOG",
}


def render(data: dict, items: list[Item], tier: int, go: bool) -> str:
    epic = data["epic"]
    lines = [
        f"## {'🟢 GO' if go else '🔴 NO-GO'} — épic #{epic['number']} « {epic.get('title', '')} »",
        f"_{TIER_TEXT.get(tier, tier)}_",
        "",
        "| | Critère | Détail |",
        "|---|---|---|",
    ]
    for it in items:
        tag = "" if it.blocking else " _(info)_"
        lines.append(f"| {it.icon} | {it.label}{tag} | {it.detail} |")
    lines.append("")
    if go:
        lines.append(
            "Prochaine étape : démo au PO, puis `po-approved` sur la PR d'intégration → merge → `40-release.sh`."
        )
    else:
        lines.append(
            "Corriger les ⛔ puis relancer `scripts/gh/32-go-no-go.sh` — le PO ne pose pas `po-approved` sur un NO-GO."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="JSON assemblé par 32-go-no-go.sh ('-' = stdin)")
    parser.add_argument("--json", action="store_true", help="sortie JSON (verdict, tier, items)")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        data = json.loads(raw)
        items, tier, go = evaluate(data)
    except (KeyError, ValueError, TypeError) as exc:
        print(f"⛔ données invalides : {exc}")
        return 2
    if args.json:
        payload = {"go": go, "tier": tier, "items": [it.__dict__ for it in items]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render(data, items, tier, go))
    return 0 if go else 1


if __name__ == "__main__":
    sys.exit(main())
