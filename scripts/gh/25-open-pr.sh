#!/usr/bin/env bash
# 25-open-pr.sh — ouvre la PR depuis la branche courante avec la BONNE base et le BON gabarit :
#   sub-feature/<epic>/<task> → feature/<epic>   (gabarit par défaut, profil CI sub-feature)
#   feature/<epic>            → main             (gabarit integration, label needs-po-review)
#   release/<epic>-<palier>   → main             (gabarit rollout)
#   hotfix/<slug>             → main             (gabarit hotfix)
#
# Usage : scripts/gh/25-open-pr.sh [numéro-issue-ou-épic] [--draft] [--web]
#   --web : ouvre le navigateur avec le formulaire pré-rempli au lieu de créer la PR en CLI
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ISSUE="" DRAFT="" WEB="false"
for a in "$@"; do
  case "$a" in
    --draft) DRAFT="--draft" ;;
    --web)   WEB="true" ;;
    -h|--help) sed -n '2,10p' "$0"; exit 1 ;;
    *) ISSUE="${a#\#}" ;;
  esac
done

HEAD="$(git rev-parse --abbrev-ref HEAD)"
BASE="$(DEFAULT_BRANCH="$DEFAULT_BRANCH" python3 "$HARNESS_ROOT/scripts/ci/check_branch.py" --head "$HEAD" --expected-base)" \
  || die "branche '$HEAD' hors convention — voir docs/process/RELEASE_PROCESS.md §Branches"

case "$HEAD" in
  sub-feature/*) TEMPLATE=".github/PULL_REQUEST_TEMPLATE.md";              LABELS="sub-task" ;;
  feature/*)     TEMPLATE=".github/PULL_REQUEST_TEMPLATE/integration.md";  LABELS="needs-po-review" ;;
  release/*)     TEMPLATE=".github/PULL_REQUEST_TEMPLATE/rollout.md";      LABELS="rollout,needs-po-review" ;;
  hotfix/*)      TEMPLATE=".github/PULL_REQUEST_TEMPLATE/hotfix.md";       LABELS="hotfix,needs-po-review" ;;
  *) die "branche '$HEAD' hors convention" ;;
esac
[ -f "$HARNESS_ROOT/$TEMPLATE" ] || die "gabarit absent : $TEMPLATE"

require_clean_tree
git push --quiet -u origin "$HEAD"

if gh pr view "$HEAD" --json url -q .url >/dev/null 2>&1; then
  ok "une PR existe déjà pour $HEAD : $(gh pr view "$HEAD" --json url -q .url)"
  exit 0
fi

# Titre : dernier commit, préfixé par l'épic
epic="$(printf '%s' "$HEAD" | cut -d/ -f2)"
case "$HEAD" in
  feature/*) TITLE="[$epic] Intégration → $DEFAULT_BRANCH" ;;
  *)         TITLE="[$epic] $(git log -1 --pretty=%s)" ;;
esac

body_file="$(mktemp)"
trap 'rm -f "$body_file"' EXIT
cp "$HARNESS_ROOT/$TEMPLATE" "$body_file"
if [ -n "$ISSUE" ]; then
  case "$HEAD" in
    feature/*)
      # L'épic reste ouvert jusqu'au nettoyage du flag : la PR d'intégration ferme l'issue de SUIVI
      track="$(tracking_issue_of "$ISSUE")"
      if [ -n "$track" ]; then
        sed -i -E "s/Closes #<numéro du suivi>/Closes #$track/; s/Refs #<numéro de l'épic>/Refs #$ISSUE/" "$body_file"
      else
        warn "pas d'issue de suivi référencée dans l'épic #$ISSUE (10-new-epic.sh la crée) — Refs #$ISSUE seulement"
        sed -i -E "s/Closes #<numéro du suivi>/Refs #$ISSUE/; s/Refs #<numéro de l'épic>/Refs #$ISSUE/" "$body_file"
      fi ;;
    *) sed -i -E "s/(Closes|Refs) #<[^>]*>/\1 #$ISSUE/" "$body_file" ;;
  esac
  case "$HEAD" in
    feature/*|release/*)  # le tier de l'épic suit la PR : po-gate exige exec-approved sur un tier 1
      tier="$(issue_tier "$ISSUE")"; LABELS="$LABELS,tier:$tier" ;;
  esac
fi

if [ "$WEB" = "true" ]; then
  # Ouvre le formulaire GitHub pré-rempli (titre + gabarit) — finir dans le navigateur
  gh pr create --base "$BASE" --head "$HEAD" --title "$TITLE" --body-file "$body_file" --web
  exit 0
fi

# shellcheck disable=SC2086  # $DRAFT volontairement non quoté (vide ou --draft)
url="$(gh pr create --base "$BASE" --head "$HEAD" --title "$TITLE" --body-file "$body_file" --label "$LABELS" $DRAFT)"
ok "PR ouverte : $url"
cat <<EOF

Prochaines étapes :
  1. Coche les lignes « - [ ] TOKEN: » de la description (la CI les vérifie à chaque édition).
  2. Demande la revue : le CODEOWNERS assigne automatiquement les bonnes équipes.
  3. Fais signer la ligne QA: par @$(printf '%s' "$QA_HANDLES" | cut -d' ' -f1 | tr -d @) une fois le scénario passé.
EOF
