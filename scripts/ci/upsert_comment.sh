#!/usr/bin/env bash
# upsert_comment.sh — crée OU met à jour un commentaire de PR identifié par un marqueur HTML caché,
# pour ne jamais empiler les commentaires automatiques à chaque relance du workflow.
#
# Usage : upsert_comment.sh <numéro-PR> "<!-- marqueur -->" "<corps markdown>"
# Env   : GH_TOKEN, GITHUB_REPOSITORY (fournis par GitHub Actions)
set -euo pipefail

pr="${1:?numéro de PR}"
marker="${2:?marqueur}"
body="${3:?corps}"
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY manquant}"

full="$marker"$'\n'"$body"
id="$(gh api "repos/$repo/issues/$pr/comments" --paginate \
        --jq ".[] | select(.body | contains(\"$marker\")) | .id" | head -n1 || true)"

if [ -n "$id" ]; then
  gh api -X PATCH "repos/$repo/issues/comments/$id" -f body="$full" >/dev/null
  echo "commentaire #$id mis à jour"
else
  gh api "repos/$repo/issues/$pr/comments" -f body="$full" >/dev/null
  echo "commentaire créé"
fi
