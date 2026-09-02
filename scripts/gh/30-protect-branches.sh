#!/usr/bin/env bash
# 30-protect-branches.sh — pose (ou met à jour) les protections du harnais via les RULESETS GitHub :
#
#   harness-main     refs/heads/main       : PR obligatoire, REVIEWS_MAIN approbations dont code owners,
#                                            approbation périmée à chaque push, threads résolus, historique linéaire,
#                                            checks requis : guard · regression · flag-check · po-gate (à jour avec main)
#   harness-feature  refs/heads/feature/*  : PR obligatoire, REVIEWS_SUBFEATURE approbation dont code owners,
#                                            checks requis : guard · lint · unit-tests · qa-smoke
#   + réglages du dépôt : squash merge uniquement, suppression auto des branches mergées.
#
# Aucun contournement (bypass) — même pour les admins : Règle 1, rien n'entre dans main sans PR.
# Prérequis : droit admin sur le dépôt. Rulesets = GitHub Free (dépôts publics) ou Team/Enterprise (privés).
#
# Usage : scripts/gh/30-protect-branches.sh [--dry-run]
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

DRY_RUN="false"
[ "${1:-}" = "--dry-run" ] && DRY_RUN="true"

# Les rulesets sont construits en Python (pas de dépendance à jq en local)
ruleset_json() { # $1 = main | feature
  python3 - "$1" "$DEFAULT_BRANCH" "$REVIEWS_MAIN" "$REVIEWS_SUBFEATURE" <<'PY'
import json, sys
kind, trunk, reviews_main, reviews_feature = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
if kind == "main":
    rs = {
        "name": "harness-main", "target": "branch", "enforcement": "active", "bypass_actors": [],
        "conditions": {"ref_name": {"include": [f"refs/heads/{trunk}"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": reviews_main,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True,
                "require_last_push_approval": True,
                "required_review_thread_resolution": True}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": c} for c in ("guard", "regression", "flag-check", "po-gate")]}},
        ],
    }
else:
    rs = {
        "name": "harness-feature", "target": "branch", "enforcement": "active", "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/feature/*"], "exclude": []}},
        "rules": [
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": reviews_feature,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [{"context": c} for c in ("guard", "lint", "unit-tests", "qa-smoke")]}},
        ],
    }
print(json.dumps(rs, indent=2))
PY
}

upsert_ruleset() { # $1 = JSON
  local json="$1" name id
  name="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])' <<<"$json")"
  if [ "$DRY_RUN" = "true" ]; then
    log "[dry-run] ruleset $name :"; printf '%s\n' "$json"; return
  fi
  id="$(gh api "repos/$REPO/rulesets" -q ".[] | select(.name==\"$name\") | .id" 2>/dev/null | head -n1 || true)"
  if [ -n "$id" ]; then
    gh api -X PUT "repos/$REPO/rulesets/$id" --input - <<<"$json" >/dev/null && ok "ruleset $name mis à jour (#$id)"
  else
    gh api -X POST "repos/$REPO/rulesets" --input - <<<"$json" >/dev/null && ok "ruleset $name créé"
  fi
}

upsert_ruleset "$(ruleset_json main)"
upsert_ruleset "$(ruleset_json feature)"

if [ "$DRY_RUN" = "true" ]; then
  log "[dry-run] réglages dépôt : squash-only, suppression auto des branches, titre de squash = titre de PR"
else
  gh api -X PATCH "repos/$REPO" \
    -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
    -F delete_branch_on_merge=true \
    -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY >/dev/null \
    && ok "dépôt : squash-only, branches supprimées après merge"
fi

cat <<EOF

Vérifie dans l'interface : Settings → Rules → Rulesets (harness-main, harness-feature).
Les checks requis portent le NOM des jobs (name:) des workflows .github/workflows/*.yml —
si tu renommes un job, mets ce script à jour et relance-le.
Gate humaine supplémentaire côté déploiement : Settings → Environments → production → Required reviewers
(EM / Tech lead) — utilisée par .github/workflows/release.yml.
EOF
