# Installation express — SpaceLabs chez un client

Objectif : d'une machine nue à une instance SpaceLabs opérationnelle **en quelques
minutes**, avec tous les services branchés. Trois couches, du plus rapide au plus complet.

## Couche 1 — SpaceLabs seul (1 commande, ~2 min)

Sur Ubuntu / WSL / macOS, avec Python 3.12+ et le CLI `claude` authentifié :

```bash
git clone https://github.com/noesis/spacelabs && cd spacelabs
bash install.sh
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000 --settings=config.settings.dev
```

`install.sh` est **idempotent** : venv, dépendances, `.env` (SECRET_KEY générée),
migrations, données de démo (`pilote` / `cockpit-local`). Rien de commité.

## Couche 2 — Machine complète depuis zéro (playbook, ~5 min)

Provisionnement type sur une Ubuntu fraîche (à jouer une fois, scriptable) :

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv git curl
# CLI agent (au choix) : Claude Code, ou un modèle LOCAL (aucune clé API)
#   modèle local : curl -fsSL https://ollama.com/install.sh | sh && ollama pull llama3.1
# OpenClaw (orchestrateur) :
#   npm i -g openclaw            # puis `openclaw` pour piloter l'installation
git clone https://github.com/noesis/spacelabs && cd spacelabs && bash install.sh
```

> Un **modèle local** (Ollama / llama.cpp) permet une machine **100 % autonome, sans
> clé API** : SpaceLabs pointe `COCKPIT_DEFAULT_CMD` / la rédaction veille vers le
> binaire local. Idéal pour un client qui veut tout on-premise.

## Couche 3 — Services & authentification

Secrets dans `.env.local` (gitignoré) :

| Service | Variable(s) | Pour |
|---|---|---|
| Veille email | `VEILLE_IMAP_USER`, `VEILLE_IMAP_PASS` | ingestion des communiqués |
| Publication blog | `ATMOSPHERE_MCP_TOKEN` | pousser les brouillons (MCP) |
| Images | `PEXELS_API_KEY` | fallback libre de droit |
| WhatsApp / Instagram | via **Chatwoot** + **Meta Business** | inbox temps réel (voir ci-dessous) |

**WhatsApp / Instagram (temps réel) — webhook natif** : SpaceLabs expose
`POST /comms/meta/webhook/` (WhatsApp Cloud API + Instagram/Messenger). Config :
```dotenv
META_VERIFY_TOKEN=<chaîne choisie, à recopier dans l'app Meta>
META_APP_SECRET=<app secret Meta>   # vérifie la signature X-Hub-Signature-256
```
Côté Meta (app → Webhooks) : URL de rappel = `https://<domaine-public>/comms/meta/webhook/`,
verify token = `META_VERIFY_TOKEN`, abonner les champs `messages`. Les DM tombent
alors dans `/comms/` (triage auto). L'app Meta se configure via le MCP
`https://mcp.facebook.com/devtools` (`claude mcp add`) ou l'UI developers.facebook.com.

Alternative clé en main (multi-canal) via Docker :
```bash
bash deploy/chatwoot/setup.sh      # déploie Chatwoot (Docker)
```
Dans les deux cas il faut un **endpoint HTTPS public** (serveur ou tunnel) pour recevoir les webhooks Meta.
L'authentification des canaux Meta passe par **ton Meta Business** (OAuth), une fois
par client. Email + Telegram fonctionnent sans Docker.

## Vérifier

```bash
make check     # migrations + Django check + tests
ruff check .   # lint
```
