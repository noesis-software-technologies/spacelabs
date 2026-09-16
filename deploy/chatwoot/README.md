# Chatwoot — inbox omnicanal (espace communication névralgique)

Chatwoot centralise **Email, WhatsApp, Telegram, Instagram DM, Messenger, SMS** dans une
seule boîte, avec tri/labels et réponses rapides. Il complète le module `apps/comms`
(qui gère déjà Email + Telegram côté SpaceLabs) pour le plein omnicanal.

## Prérequis
Docker (absent pour l'instant). Le plus simple sous WSL2 :
1. Installer **Docker Desktop** : https://www.docker.com/products/docker-desktop/
2. Settings → Resources → **WSL Integration** → activer la distro → Apply & Restart.
   *(ou, dans WSL : `curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER`)*

## Lancement
```bash
bash deploy/chatwoot/setup.sh
```
→ Chatwoot sur http://localhost:3000 (crée le compte admin au 1er accès).

## Branchement des canaux (après boot)
- **Email** : Inbox → Email → adresse de forwarding, ou IMAP (`spacelabs.ai.pro@gmail.com` + app password).
- **Telegram** : Inbox → Telegram → coller le **token du bot** (BotFather).
- **WhatsApp** : nécessite un **WhatsApp Business + API Cloud (Meta)**.
- **Instagram DM / Messenger** : compte **Business/Créateur** + app Meta (validation).
- **SMS** : via **Twilio** (payant).
- **TikTok DM** : pas d'API officielle → non couvert.

## Notes
- Secrets (SECRET_KEY_BASE, POSTGRES_PASSWORD) générés par le script dans `~/chatwoot/.env` — jamais commités.
- Postgres/Redis internes au compose ; seul le web (3000) est exposé.
