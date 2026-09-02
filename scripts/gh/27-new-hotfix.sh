#!/usr/bin/env bash
# 27-new-hotfix.sh — démarrer un correctif urgent (S1 / S2) : hotfix/<slug> depuis main, lié au bug.
#
#   Mêmes gates que tout le reste, profil réduit (TICKET TESTS ROLLBACK), go PO asynchrone, puis tag `patch`
#   et report du correctif dans les feature/* ouvertes. Un hotfix est une PR : jamais de push direct sur main.
#
# Usage : scripts/gh/27-new-hotfix.sh <slug> [numéro-du-bug]
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ $# -ge 1 ] || { sed -n '2,8p' "$0"; exit 1; }
SLUG="$(slug "$1")"; BUG="${2:-}"; BUG="${BUG#\#}"
BRANCH="hotfix/$SLUG"

require_clean_tree
git fetch --quiet origin
remote_branch_exists "$BRANCH" && die "origin/$BRANCH existe déjà : git switch $BRANCH (ou choisis un autre slug)"
if [ -n "$BUG" ]; then
  issue_has_label "$BUG" "bug" || warn "l'issue #$BUG ne porte pas le label bug"
  gh issue edit "$BUG" --add-label hotfix >/dev/null 2>&1 || true
  gh issue develop "$BUG" --name "$BRANCH" --base "$DEFAULT_BRANCH" >/dev/null
  git fetch --quiet origin "$BRANCH" && git switch --quiet --track "origin/$BRANCH"
  ok "branche $BRANCH créée sur GitHub, liée au bug #$BUG, récupérée en local"
else
  git switch --quiet -c "$BRANCH" "origin/$DEFAULT_BRANCH"
  ok "branche $BRANCH créée depuis origin/$DEFAULT_BRANCH"
fi

cat <<EOT

Tu es sur $BRANCH. Procédure (docs/process/RELEASE_PROCESS.md §3) :
  1. Écris d'abord le test qui ÉCHOUE sur le bug, puis le correctif minimal (pas de refactor).
  2. git add -A && git commit -m "fix: <résumé>${BUG:+ (#$BUG)}" && git push
  3. scripts/gh/25-open-pr.sh ${BUG:-<bug>}        # PR → $DEFAULT_BRANCH, gabarit hotfix, label needs-po-review
  4. Après merge : scripts/gh/40-release.sh patch   # tag → prod (approbation EM) ; smoke test QA automatique
  5. Reporter dans les feature/* ouvertes : git switch feature/<epic> && git merge origin/$DEFAULT_BRANCH && git push
Rappel : si le bug est derrière un flag, le repli immédiat est FLAG_<NOM>=off — le hotfix vient après.
EOT
