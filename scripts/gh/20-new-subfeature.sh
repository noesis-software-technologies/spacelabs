#!/usr/bin/env bash
# 20-new-subfeature.sh — démarre une sous-tâche (rôle : développeur d'une sub-team).
#
#   crée sub-feature/<epic>/<task> depuis origin/feature/<epic>, la pousse, et si un numéro
#   d'issue est donné, la lie à l'issue (« Development » dans la barre latérale GitHub).
#
# Usage : scripts/gh/20-new-subfeature.sh <epic-slug> <task-slug-ou-titre> [numéro-issue]
#   ex.  : scripts/gh/20-new-subfeature.sh billing-dashboard "Billing API" 57
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ $# -ge 2 ] || { sed -n '2,9p' "$0"; exit 1; }
EPIC_SLUG="$(slug "$1")"
TASK_SLUG="$(slug "$2")"
ISSUE="${3:-}"
BASE="feature/$EPIC_SLUG"
BRANCH="sub-feature/$EPIC_SLUG/$TASK_SLUG"

require_clean_tree
git fetch --quiet origin
remote_branch_exists "$BASE" \
  || die "origin/$BASE n'existe pas — le tech lead doit d'abord lancer : scripts/gh/10-new-epic.sh --slug $EPIC_SLUG ..."

if remote_branch_exists "$BRANCH"; then
  log "$BRANCH existe déjà sur origin — bascule dessus"
  git switch --quiet "$BRANCH" 2>/dev/null || git switch --quiet --track "origin/$BRANCH"
  git pull --quiet --ff-only origin "$BRANCH"
elif [ -n "$ISSUE" ] && gh issue develop "$ISSUE" --name "$BRANCH" --base "$BASE" >/dev/null 2>&1; then
  # Branche créée côté GitHub ET liée à l'issue (barre « Development »)
  git fetch --quiet origin
  git switch --quiet --track "origin/$BRANCH"
  ok "branche $BRANCH créée sur GitHub, liée à #$ISSUE, récupérée en local"
else
  [ -n "$ISSUE" ] && warn "gh issue develop indisponible — création git classique (mets 'Closes #$ISSUE' dans la PR)"
  git switch --quiet -c "$BRANCH" "origin/$BASE"
  git push --quiet -u origin "$BRANCH"
  ok "branche $BRANCH créée depuis origin/$BASE et poussée"
fi

cat <<EOF

Tu es sur $BRANCH (base : $BASE). Boucle de travail :
  git add -A && git commit -m "feat($EPIC_SLUG): …"     # petits commits
  git push                                             # à chaque étape
  scripts/gh/25-open-pr.sh ${ISSUE:-<numéro-issue>}       # ouvre la PR vers $BASE avec la checklist
Rappel Règle 3 : tout le nouveau code derrière le flag \`$(flag_name "$EPIC_SLUG")\`.
EOF
