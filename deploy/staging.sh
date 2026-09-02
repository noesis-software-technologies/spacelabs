#!/usr/bin/env bash
# deploy/staging.sh — hook de déploiement staging (contrat : deploy/README.md). Remplacer le TODO par l'infra du projet.
set -euo pipefail
: "${DEPLOY_ENV:=staging}" "${GIT_SHA:=$(git rev-parse HEAD)}"
echo "▶ déploiement $DEPLOY_ENV — commit $GIT_SHA${TAG:+ (tag $TAG)}"
# --- exemples (un seul à garder) --------------------------------------------------------------
# ssh + systemd : ssh "deploy@$DEPLOY_ENV.example.com" "cd /srv/app && git fetch -q && git checkout -q $GIT_SHA && ./bin/release.sh"
# docker compose : docker compose -f compose.$DEPLOY_ENV.yml pull && docker compose -f compose.$DEPLOY_ENV.yml up -d --remove-orphans
# PaaS          : flyctl deploy --config fly.$DEPLOY_ENV.toml --image-label "$GIT_SHA"
echo "::notice::TODO deploy/staging.sh : brancher l'infra (voir deploy/README.md)"
