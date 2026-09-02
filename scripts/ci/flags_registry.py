#!/usr/bin/env python3
"""Registre des feature flags — ``config/feature_flags.yml`` est la source de vérité.

Sous-commandes :
  add    --name X --epic '#42' --pod growth --owner @org/pod-growth [--max-age 90]
         → déclare X à OFF (code 0), ou 3 si déjà déclaré, 1 si nom invalide
  set    --name X --state off|rollout|on|permanent [--percentage N] [--allow-user login]...
         → change l'état (palier de rollout) ; 1 si inconnu / invalide
  check  [--code-root .] [--max-age 90] [--strict] [--exclude dir]...
         → 1 si un flag utilisé dans le code n'est pas déclaré (ou registre invalide),
           2 si des flags sont périmés ET --strict, 0 sinon (périmés = avertissements)
  stale  [--max-age 90] [--json]
         → liste les flags périmés (état ≠ permanent et échéance dépassée) ; code 0

Nom de flag : ``<slug>_v<n>`` en snake_case (ex. billing_dashboard_v1) — utilisable tel quel
en Python, en variable d'environnement (FLAG_BILLING_DASHBOARD_V1) et dans les templates Django
(``{% if flags.billing_dashboard_v1 %}``, où le tiret est interdit).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "config" / "feature_flags.yml"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*_v\d+$")
STATES = ("off", "rollout", "on", "permanent")
DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "tests",
    "scripts",
    "static",
    "media",
    "dist",
    "build",
}

# Utilisations dans le code : is_enabled("x"), flag_required("x"), {% if flags.x %}
_PY_USE = re.compile(r"\b(?:is_enabled|flag_required)\(\s*[\"']([a-z][a-z0-9_]*_v\d+)[\"']")
_TPL_USE = re.compile(r"\bflags\.([a-z][a-z0-9_]*_v\d+)\b")


def _today() -> dt.date:
    forced = os.environ.get("HARNESS_TODAY")  # tests / reproductibilité
    return dt.date.fromisoformat(forced) if forced else dt.date.today()


def _norm_state(value: object) -> str:
    # YAML 1.1 lit `off`/`on` non quotés comme des booléens → on normalise
    if value is True:
        return "on"
    if value is False:
        return "off"
    return str(value)


def load(path: Path = DEFAULT_REGISTRY) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    flags = data.get("flags") or []
    for f in flags:
        f["state"] = _norm_state(f.get("state", "off"))
    return flags


def save(flags: list[dict], path: Path = DEFAULT_REGISTRY) -> None:
    header = (
        "# Registre des feature flags — SOURCE DE VÉRITÉ (docs/process/FEATURE_FLAGS.md).\n"
        "# Modifié par scripts/ci/flags_registry.py (add / set) ; états : off | rollout | on | permanent.\n"
        "# Toujours quoter off/on (YAML 1.1 les lirait comme des booléens).\n"
    )
    body = yaml.safe_dump({"flags": flags}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body, encoding="utf-8")


def validate(flags: list[dict]) -> list[str]:
    """Erreurs de schéma du registre (liste vide = valide)."""
    errors: list[str] = []
    seen: set[str] = set()
    for f in flags:
        name = str(f.get("name", ""))
        if not NAME_RE.match(name):
            errors.append(f"nom invalide : {name!r} (attendu <slug>_v<n> en snake_case)")
        if name in seen:
            errors.append(f"doublon : {name}")
        seen.add(name)
        if f.get("state") not in STATES:
            errors.append(f"{name}: état {f.get('state')!r} invalide (choix : {', '.join(STATES)})")
        pct = f.get("percentage", 0)
        if not isinstance(pct, int) or not 0 <= pct <= 100:
            errors.append(f"{name}: percentage doit être un entier 0..100")
        for key in ("created",):
            try:
                dt.date.fromisoformat(str(f.get(key)))
            except ValueError:
                errors.append(f"{name}: {key} doit être une date ISO (AAAA-MM-JJ)")
    return errors


def add(
    name: str, epic: str, pod: str, owner: str, max_age: int, path: Path = DEFAULT_REGISTRY, description: str = ""
) -> int:
    if not NAME_RE.match(name):
        print(f"⛔ nom de flag invalide : {name} (attendu <slug>_v<n>, ex. billing_dashboard_v1)")
        return 1
    flags = load(path)
    if any(f.get("name") == name for f in flags):
        print(f"ℹ️  flag {name} déjà déclaré")
        return 3
    today = _today()
    flags.append(
        {
            "name": name,
            "epic": epic,
            "pod": pod,
            "owner": owner,
            "state": "off",
            "percentage": 0,
            "allow_users": [],
            "created": today.isoformat(),
            "cleanup_by": (today + dt.timedelta(days=max_age)).isoformat(),
            "description": description,
        }
    )
    save(flags, path)
    print(f"✅ flag {name} déclaré à OFF (nettoyage prévu {flags[-1]['cleanup_by']})")
    return 0


def set_state(
    name: str, state: str, percentage: int | None, allow_users: list[str], path: Path = DEFAULT_REGISTRY
) -> int:
    if state not in STATES:
        print(f"⛔ état invalide : {state} (choix : {', '.join(STATES)})")
        return 1
    flags = load(path)
    for f in flags:
        if f.get("name") == name:
            f["state"] = state
            if percentage is not None:
                if not 0 <= percentage <= 100:
                    print("⛔ percentage doit être entre 0 et 100")
                    return 1
                f["percentage"] = percentage
            elif state == "on":
                f["percentage"] = 100
            elif state == "off":
                f["percentage"] = 0
            if allow_users:
                f["allow_users"] = sorted(set(f.get("allow_users") or []) | set(allow_users))
            # Date de lancement (palier 100) : déclenche la revue post-launch J+N (workflow flag-hygiene)
            if state in ("on", "permanent"):
                f.setdefault("released_at", _today().isoformat())
            elif state == "off":
                f.pop("released_at", None)
            save(flags, path)
            print(f"✅ {name} → {state} ({f['percentage']} %)")
            return 0
    print(f"⛔ flag inconnu : {name}")
    return 1


def used_in_code(code_root: Path, excludes: set[str]) -> dict[str, list[str]]:
    """{flag: [fichiers]} pour chaque flag référencé dans le code (py / html / txt)."""
    found: dict[str, list[str]] = {}
    for p in code_root.rglob("*"):
        if not p.is_file() or p.suffix not in {".py", ".html", ".txt", ".jinja", ".j2"}:
            continue
        if any(part in excludes for part in p.relative_to(code_root).parts):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        pattern = _TPL_USE if p.suffix != ".py" else _PY_USE
        for name in pattern.findall(text):
            found.setdefault(name, []).append(str(p.relative_to(code_root)))
    return found


def due_reviews(flags: list[dict], after_days: int) -> list[dict]:
    """Flags lancés (on/permanent) depuis au moins ``after_days`` jours : revue post-launch à ouvrir."""
    today = _today()
    out = []
    for f in flags:
        released = f.get("released_at")
        if str(f.get("state")).lower() not in ("on", "permanent", "true") or not released:
            continue
        try:
            since = (today - dt.date.fromisoformat(str(released))).days
        except ValueError:
            continue
        if since >= after_days:
            out.append({**f, "days_since": since})
    return out


def stale_flags(flags: list[dict], max_age: int) -> list[dict]:
    today = _today()
    out = []
    for f in flags:
        if f.get("state") == "permanent":
            continue
        deadline = f.get("cleanup_by")
        try:
            limit = (
                dt.date.fromisoformat(str(deadline))
                if deadline
                else (dt.date.fromisoformat(str(f.get("created"))) + dt.timedelta(days=max_age))
            )
        except ValueError:
            continue
        if today > limit:
            out.append({**f, "deadline": limit.isoformat(), "days_over": (today - limit).days})
    return out


def check(code_root: Path, max_age: int, strict: bool, excludes: set[str], path: Path = DEFAULT_REGISTRY) -> int:
    flags = load(path)
    errors = validate(flags)
    if errors:
        print("⛔ registre invalide :\n  - " + "\n  - ".join(errors))
        return 1
    declared = {f["name"] for f in flags}
    used = used_in_code(code_root, excludes)
    undeclared = {n: files for n, files in used.items() if n not in declared}
    rc = 0
    if undeclared:
        print("⛔ flags utilisés dans le code mais absents de config/feature_flags.yml :")
        for n, files in sorted(undeclared.items()):
            print(f"  - {n}  ({', '.join(sorted(set(files))[:5])})")
        print("  → scripts/ci/flags_registry.py add --name <flag> --epic '#n' --pod <pod> --owner <@org/team>")
        rc = 1
    unused = sorted(declared - set(used))
    for n in unused:
        print(f"::notice::flag {n} déclaré mais introuvable dans le code (normal avant le 1er commit fonctionnel)")
    stale = stale_flags(flags, max_age)
    for f in stale:
        print(
            f"::warning::flag {f['name']} périmé depuis {f['days_over']} j "
            f"(état {f['state']}, échéance {f['deadline']}) — à nettoyer"
        )
    if stale and strict and rc == 0:
        rc = 2
    if rc == 0:
        print(
            f"✅ registre cohérent : {len(declared)} flag(s) déclaré(s), {len(used)} utilisé(s), {len(stale)} périmé(s)"
        )
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--epic", required=True)
    p_add.add_argument("--pod", required=True)
    p_add.add_argument("--owner", required=True)
    p_add.add_argument("--max-age", type=int, default=90)
    p_add.add_argument("--description", default="")

    p_set = sub.add_parser("set")
    p_set.add_argument("--name", required=True)
    p_set.add_argument("--state", required=True, choices=STATES)
    p_set.add_argument("--percentage", type=int)
    p_set.add_argument("--allow-user", action="append", default=[])

    p_check = sub.add_parser("check")
    p_check.add_argument("--code-root", type=Path, default=ROOT)
    p_check.add_argument("--max-age", type=int, default=90)
    p_check.add_argument("--strict", action="store_true")
    p_check.add_argument("--exclude", action="append", default=[])

    p_review = sub.add_parser("review", help="flags lancés depuis N jours → revue post-launch due")
    p_review.add_argument("--after", type=int, default=7)
    p_review.add_argument("--json", action="store_true")

    p_stale = sub.add_parser("stale")
    p_stale.add_argument("--max-age", type=int, default=90)
    p_stale.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "add":
        return add(args.name, args.epic, args.pod, args.owner, args.max_age, args.registry, args.description)
    if args.cmd == "set":
        return set_state(args.name, args.state, args.percentage, args.allow_user, args.registry)
    if args.cmd == "check":
        return check(args.code_root, args.max_age, args.strict, DEFAULT_EXCLUDES | set(args.exclude), args.registry)
    if args.cmd == "review":
        due = due_reviews(load(args.registry), args.after)
        if args.json:
            print(json.dumps(due, ensure_ascii=False))
        else:
            for f in due:
                print(f"{f['name']}: lancé le {f['released_at']} (J+{f['days_since']}) — revue post-launch due")
            if not due:
                print("aucune revue post-launch due")
        return 0
    if args.cmd == "stale":
        stale = stale_flags(load(args.registry), args.max_age)
        if args.json:
            print(json.dumps(stale, ensure_ascii=False, default=str))
        else:
            for f in stale:
                print(f"{f['name']}\t{f['state']}\t{f['deadline']}\t+{f['days_over']} j\t{f.get('owner', '')}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
