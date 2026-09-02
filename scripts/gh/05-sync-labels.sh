#!/usr/bin/env bash
# 05-sync-labels.sh — crée/met à jour les labels du harnais (.github/labels.tsv + un label pod:<slug>
# par pod de harness.config.sh). Idempotent : --force met à jour couleur et description.
#
# Usage : scripts/gh/05-sync-labels.sh
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

LABELS_FILE="$HARNESS_ROOT/.github/labels.tsv"
[ -f "$LABELS_FILE" ] || die "fichier absent : $LABELS_FILE"

sync_label() { # $1 name, $2 color (hex sans #), $3 description
  gh label create "$1" --color "$2" --description "$3" --force >/dev/null \
    && log "label '$1'"
}

# Fichier TSV : name<TAB>color<TAB>description ; lignes vides / # ignorées
while IFS=$'\t' read -r name color desc; do
  [ -z "$name" ] && continue
  [[ "$name" == \#* ]] && continue
  sync_label "$name" "$color" "$desc"
done <"$LABELS_FILE"

for pod in "${PODS[@]}"; do
  sync_label "pod:$pod" "C2E0C6" "Pod $pod"
done

ok "labels synchronisés sur $REPO"
