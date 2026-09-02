#!/usr/bin/env bash
# 50-push-vars.sh — pousse harness.config.sh vers les VARIABLES du dépôt (lues par les workflows
# via ${{ vars.X }}). À relancer après chaque modification de harness.config.sh.
#
# Les SECRETS ne passent pas par ici (jamais dans un fichier versionné) :
#   gh secret set SLACK_WEBHOOK_URL      # webhook du canal PM/PO (optionnel)
#
# Usage : scripts/gh/50-push-vars.sh
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

push_var() { # $1 nom, $2 valeur
  gh variable set "$1" --body "$2" >/dev/null && log "vars.$1 = $2"
}

push_var PO_HANDLES            "$PO_HANDLES"
push_var QA_HANDLES            "$QA_HANDLES"
push_var PMM_HANDLES           "$PMM_HANDLES"
push_var PO_APPROVERS          "$PO_APPROVERS"
push_var PO_GATE_STRICT        "$PO_GATE_STRICT"
push_var EXEC_APPROVERS        "$EXEC_APPROVERS"
push_var FLAG_MAX_AGE_DAYS     "$FLAG_MAX_AGE_DAYS"
push_var POST_LAUNCH_REVIEW_DAYS "$POST_LAUNCH_REVIEW_DAYS"
push_var PROD_HEALTH_URL       "$PROD_HEALTH_URL"
push_var E2E_ENABLED           "$E2E_ENABLED"
push_var DJANGO_SETTINGS_MODULE "$DJANGO_SETTINGS_MODULE"

ok "variables poussées sur $REPO"
[ -z "$PO_APPROVERS" ] && warn "PO_APPROVERS vide : la simple présence du label po-approved suffira (renseigne les logins PO/PM dans harness.config.sh)"
if ! gh secret list 2>/dev/null | grep -q '^SLACK_WEBHOOK_URL'; then
  log "secret SLACK_WEBHOOK_URL absent — notifications Slack désactivées (gh secret set SLACK_WEBHOOK_URL pour activer)"
fi
