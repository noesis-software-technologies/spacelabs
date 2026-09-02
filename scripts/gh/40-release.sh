#!/usr/bin/env bash
# 40-release.sh — coupe une release (rôle : EM / Tech lead, après go PO) :
#   1. main à jour et VERT (tous les checks du dernier commit réussis)
#   2. tag semver annoté vX.Y.Z (bump patch|minor|major depuis le dernier tag v*)
#   3. push du tag → .github/workflows/release.yml crée la GitHub Release (notes auto)
#      puis déploie via l'environnement `production` (approbation EM/Tech lead)
#
# Rappel trunk-based : déployer ≠ releaser. Le code part avec ses flags à OFF ;
# la release produit = un palier de rollout (release/<epic>-<palier> → main, gate PO).
#
# Usage : scripts/gh/40-release.sh [patch|minor|major] [--force]
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

BUMP="patch" FORCE="false"
for a in "$@"; do
  case "$a" in
    patch|minor|major) BUMP="$a" ;;
    --force) FORCE="true" ;;
    *) sed -n '2,12p' "$0"; exit 1 ;;
  esac
done

require_clean_tree
git switch --quiet "$DEFAULT_BRANCH"
git pull --quiet --ff-only origin "$DEFAULT_BRANCH"
sha="$(git rev-parse HEAD)"

# 1. main vert ?
failing="$(gh api "repos/$REPO/commits/$sha/check-runs" -q '.check_runs[] | select(.conclusion != "success" and .conclusion != "skipped" and .conclusion != "neutral") | .name' 2>/dev/null || true)"
if [ -n "$failing" ] && [ "$FORCE" != "true" ]; then
  die "main n'est pas vert sur $sha — checks non réussis : $(tr '\n' ' ' <<<"$failing")(--force pour passer outre)"
fi

# 2. version suivante
last="$(git describe --tags --abbrev=0 --match 'v*' 2>/dev/null || echo v0.0.0)"
IFS=. read -r major minor patch <<<"${last#v}"
case "$BUMP" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
esac
new="v$major.$minor.$patch"

log "release $last → $new sur $DEFAULT_BRANCH@${sha:0:7}"
read -r -p "Confirmer le tag $new ? [y/N] " answer
[ "$answer" = "y" ] || [ "$answer" = "Y" ] || die "annulé"

# 3. tag + push (déclenche release.yml)
git tag -a "$new" -m "release $new"
git push --quiet origin "$new"
ok "tag $new poussé — suivre : gh run watch (workflow release)"
[ -n "$PMM_HANDLES" ] && log "pense à prévenir $PMM_HANDLES : notes de release générées automatiquement"
