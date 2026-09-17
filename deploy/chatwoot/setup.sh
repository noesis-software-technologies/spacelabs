#!/usr/bin/env bash
# Déploiement Chatwoot (inbox omnicanal) — À LANCER UNE FOIS DOCKER INSTALLÉ.
# Usage : bash deploy/chatwoot/setup.sh
set -euo pipefail

DIR="$HOME/chatwoot"
mkdir -p "$DIR" && cd "$DIR"

command -v docker >/dev/null || { echo "❌ Docker introuvable. Installe Docker Desktop + WSL integration, puis relance."; exit 1; }

echo "→ Récupération des fichiers officiels Chatwoot…"
[ -f docker-compose.yaml ] || curl -fsSL -o docker-compose.yaml https://raw.githubusercontent.com/chatwoot/chatwoot/develop/docker-compose.production.yaml
[ -f .env ] || curl -fsSL -o .env https://raw.githubusercontent.com/chatwoot/chatwoot/develop/.env.example

# Config minimale locale (idempotent)
set_env () { grep -q "^$1=" .env && sed -i "s|^$1=.*|$1=$2|" .env || echo "$1=$2" >> .env; }
set_env SECRET_KEY_BASE "$(openssl rand -hex 64)"
set_env FRONTEND_URL "http://localhost:3000"
set_env INSTALLATION_ENV docker
set_env RAILS_ENV production
set_env NODE_ENV production
set_env ENABLE_ACCOUNT_SIGNUP false
set_env POSTGRES_PASSWORD "$(openssl rand -hex 16)"
set_env FORCE_SSL false

echo "→ Préparation de la base (première fois, télécharge les images ~quelques min)…"
docker compose run --rm rails bundle exec rails db:chatwoot_prepare

echo "→ Démarrage des services…"
docker compose up -d

echo "✅ Chatwoot démarre sur http://localhost:3000 (laisse ~1 min au 1er boot)."
echo "   Crée ton compte admin, puis on branche Email + Telegram."
