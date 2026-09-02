#!/usr/bin/env bash
# lib.sh — helpers communs aux scripts scripts/gh/*.sh. À sourcer, pas à exécuter.
set -euo pipefail

HARNESS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_ROOT="$(cd "$HARNESS_LIB_DIR/../.." && pwd)"
export HARNESS_ROOT

# shellcheck source=../../harness.config.sh
source "$HARNESS_ROOT/harness.config.sh"

log()  { printf '▶ %s\n' "$*"; }
ok()   { printf '✅ %s\n' "$*"; }
warn() { printf '⚠️  %s\n' "$*" >&2; }
die()  { printf '✗ %s\n' "$*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "'$1' est requis — $2"
}

need gh  "installe GitHub CLI : https://cli.github.com puis 'gh auth login'"
need git "installe git"
need python3 "python 3.10+ requis pour scripts/ci/*.py"

gh auth status >/dev/null 2>&1 || die "GitHub CLI non authentifié — lance : gh auth login"

# Dépôt courant au format owner/name (surchargeable : REPO=owner/name script.sh)
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)}"
[ -n "$REPO" ] || die "impossible de déterminer le dépôt — lance le script depuis un clone, ou REPO=owner/name"
export REPO

# kebab-case strict : "DB Migrations" → "db-migrations"
slug() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | iconv -f utf-8 -t ascii//TRANSLIT 2>/dev/null \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

# nom de flag : "billing-dashboard" → "billing_dashboard_v1"
flag_name() { printf '%s_v1' "${1//-/_}"; }

# Refuse de continuer si le clone a des modifications non commitées
require_clean_tree() {
  [ -z "$(git status --porcelain)" ] || die "arbre de travail non propre — commite ou 'git stash' avant de continuer"
}

# Vérifie qu'une branche existe sur origin
remote_branch_exists() { git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1; }

# Numéro d'issue/PR depuis une URL GitHub
number_from_url() { printf '%s' "${1##*/}"; }

# Une issue porte-t-elle un label ?
# Tier de lancement d'un épic : label tier:N, sinon dropdown « Tier de lancement » du formulaire, sinon 2
issue_tier() { # $1 = numéro d'épic
  local t
  t="$(gh issue view "$1" --json labels -q '.labels[].name' 2>/dev/null | sed -nE 's/^tier:([123])$/\1/p' | head -n1)"
  [ -n "$t" ] || t="$(gh issue view "$1" --json body -q .body 2>/dev/null | tr -d '\r' | sed -nE '/^### Tier de lancement/{n;n;s/^[[:space:]]*([123]).*/\1/p;}' | head -n1)"
  printf '%s' "${t:-2}"
}

# Numéro de l'issue de suivi d'intégration écrit dans le corps de l'épic par 10-new-epic.sh (vide si absent)
tracking_issue_of() { # $1 = numéro d'épic
  gh issue view "$1" --json body -q .body 2>/dev/null | sed -nE "s/.*Suivi d'intégration\*\* : #([0-9]+).*/\1/p" | head -n1
}

issue_has_label() { # $1 = numéro, $2 = label
  gh issue view "$1" --json labels -q '.labels[].name' | grep -qx -- "$2"
}
