#!/usr/bin/env bash
# 35-rollout.sh — ouvre un PALIER DE ROLLOUT : c'est la « release produit » en trunk-based.
#   Crée release/<epic>-<palier> depuis main, passe le flag <epic>_v1 à l'état voulu dans
#   config/feature_flags.yml, commite, pousse et ouvre la PR → main (gabarit rollout, gate PO).
#   Le déploiement de main propage le nouvel état du registre (cf. docs/process/FEATURE_FLAGS.md).
#
# Usage : scripts/gh/35-rollout.sh <epic-slug> <palier> [--allow-user login]...
#   <palier> : internal | 10 | 25 | 50 | 100 | off
#     internal → state=rollout, 0 %, liste blanche (--allow-user) ; 10/25/50 → rollout N % ;
#     100 → on ; off → kill switch (repli)
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ $# -ge 2 ] || { sed -n '2,12p' "$0"; exit 1; }
EPIC_SLUG="$(slug "$1")"
STEP="$2"
shift 2
ALLOW=()
while [ $# -gt 0 ]; do
  case "$1" in
    --allow-user) ALLOW+=(--allow-user "$2"); shift 2 ;;
    *) die "option inconnue : $1" ;;
  esac
done

FLAG="$(flag_name "$EPIC_SLUG")"
case "$STEP" in
  internal) SET=(--state rollout --percentage 0) ;;
  10|25|50|75) SET=(--state rollout --percentage "$STEP") ;;
  100|on)   SET=(--state on) ; STEP="100" ;;
  off)      SET=(--state off) ;;
  *) die "palier inconnu : $STEP (internal | 10 | 25 | 50 | 75 | 100 | off)" ;;
esac
BRANCH="release/$EPIC_SLUG-$STEP"

require_clean_tree
git fetch --quiet origin
remote_branch_exists "$BRANCH" && die "origin/$BRANCH existe déjà — une PR de palier est probablement ouverte : gh pr view $BRANCH"
git show-ref --verify --quiet "refs/heads/$BRANCH" && die "la branche locale $BRANCH existe déjà (obsolète ? git branch -D $BRANCH)"
git switch --quiet -c "$BRANCH" "origin/$DEFAULT_BRANCH"
abort() { git checkout --quiet -- config/feature_flags.yml; git switch --quiet "$DEFAULT_BRANCH"; git branch -D "$BRANCH" >/dev/null; die "$1"; }
python3 "$HARNESS_ROOT/scripts/ci/flags_registry.py" set --name "$FLAG" "${SET[@]}" "${ALLOW[@]}" \
  || abort "registre non modifié (flag inconnu sur $DEFAULT_BRANCH ? l'intégration doit être mergée d'abord)"
git diff --quiet -- config/feature_flags.yml \
  && abort "le flag $FLAG est déjà dans cet état sur $DEFAULT_BRANCH — rien à releaser"
git add config/feature_flags.yml
git commit --quiet -m "release($EPIC_SLUG): $FLAG → palier $STEP"
git push --quiet -u origin "$BRANCH"
ok "palier $STEP commité sur $BRANCH"

epic_issue="$(python3 - "$HARNESS_ROOT/config/feature_flags.yml" "$FLAG" <<'PY'
import sys, yaml
flags = (yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}).get("flags") or []
print(next((str(f.get("epic", "")).lstrip("#") for f in flags if f.get("name") == sys.argv[2]), ""))
PY
)"
"$HARNESS_LIB_DIR/25-open-pr.sh" "${epic_issue:-}"
log "à faire dans la PR : critères de passage au palier suivant + métriques surveillées (North Star + guardrails)"
