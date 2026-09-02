#!/usr/bin/env bash
# 00-bootstrap-teams.sh — crée les équipes GitHub de l'organigramme (harness.config.sh : TEAMS + PODS)
# et leur donne accès au dépôt courant. Idempotent (une équipe existante est simplement rattachée).
#
# Prérequis : être propriétaire (owner) de l'organisation $ORG. Sans org (dépôt perso),
# GitHub n'a pas d'équipes : remplace alors les @org/équipe de CODEOWNERS par des @logins.
#
# Usage : scripts/gh/00-bootstrap-teams.sh [--dry-run]
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

DRY_RUN="false"
[ "${1:-}" = "--dry-run" ] && DRY_RUN="true"

create_team() { # $1 slug, $2 description, $3 permission
  local team="$1" desc="$2" perm="$3"
  if [ "$DRY_RUN" = "true" ]; then
    log "[dry-run] équipe @$ORG/$team ($perm) — $desc"
    return
  fi
  if gh api "orgs/$ORG/teams/$team" >/dev/null 2>&1; then
    log "équipe @$ORG/$team existe déjà"
  else
    gh api "orgs/$ORG/teams" -f name="$team" -f description="$desc" -f privacy=closed >/dev/null \
      && ok "équipe @$ORG/$team créée"
  fi
  gh api -X PUT "orgs/$ORG/teams/$team/repos/$REPO" -f permission="$perm" >/dev/null \
    && ok "  ↳ accès $perm sur $REPO"
}

log "Organisation : $ORG — dépôt : $REPO"

for entry in "${TEAMS[@]}"; do
  IFS='|' read -r team desc perm <<<"$entry"
  create_team "$team" "$desc" "$perm"
done

for pod in "${PODS[@]}"; do
  create_team "pod-$pod" "Pod $pod — squad cross-fonctionnelle (PM, design, eng, QA, growth)" "push"
done

ok "équipes prêtes. Ajoute les membres : gh api -X PUT orgs/$ORG/teams/<slug>/memberships/<login>"
