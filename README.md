# SpaceLabs

🌍 **Français** · [English](README.en.md)

[![CI](https://github.com/noesis/spacelabs/actions/workflows/ci.yml/badge.svg)](https://github.com/noesis/spacelabs/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-092E20.svg)](https://www.djangoproject.com/)
[![Ruff](https://img.shields.io/badge/lint-ruff-orange.svg)](https://github.com/astral-sh/ruff)

**Le cockpit web local-first pour piloter une flotte d'agents IA depuis votre navigateur.**

Des dizaines d'agents qui codent, testent et livrent en parallèle sur votre machine.
Vous les observez du coin de l'œil, vous intervenez quand vous le décidez, vous
reprenez la main à tout instant.

![Cockpit Braingod Team — 6 agents en parallèle](docs/screenshots/braingod_running.png)

---

## L'objectif

Les agents IA de développement sont devenus autonomes. Le problème n'est plus de
*lancer* un agent — c'est de **piloter une flotte** :

- où est chaque agent ? dans quel repo ? sur quelle tâche ?
- lequel a fini, lequel bloque, lequel déraille ?
- comment reprendre la main sans perdre le contexte ?

SpaceLabs répond à ces trois questions avec un principe simple : **un pane par
agent, un mur d'agents par écran**. La sortie des agents est le contenu ;
l'interface est un cadre et s'efface.

## Ce que ça fait

| Capacité | Détail |
|---|---|
| **Panes terminal temps réel** | Vrai PTY dans le navigateur (WebSocket + Channels), buffer rejoué à la reconnexion |
| **Reprise de session** | F5, crash navigateur, redémarrage serveur : la grille se restaure, l'historique revient, `--continue` relance exactement où c'était |
| **Multi-workspaces** | Plusieurs projets côte à côte, plafond configurable par workspace et par compte |
| **Chat headless** | Mode conversationnel `stream-json` : bulles, outils repliables, coût/durée, persistance intégrale |
| **Vue spectateur** | `/observer/` — SSE anonyme read-only, rédaction serveur des panes privés, pensé pour le live streaming |
| **Commande vocale** | Push-to-talk fr-FR par pane ; option 100% offline via CrisperWhisper |
| **Missions & Tasker** | Orchestration déclarative : un Master Tasker distribue le travail aux agents |
| **Exploitation** | Celery + beat : faucheur de zombies, snapshots d'usage, archivage, réconciliation au boot |

![Guillaume Studio — second workspace, sessions indépendantes](docs/screenshots/guillaume_studio.png)

## Surfaces web

| URL | Rôle |
|---|---|
| `/dashboard/` | **Cockpit central** — sidebar + tuiles KPI live, thème clair/sombre |
| `/` | Landing publique — constellation neurale (Three.js) |
| `/vitrine/` | Vitrine produits — portfolio animé, focus desktop |
| `/veille/` | **Veille éditoriale** — RP triées → constellation de blogs *13 Atmosphère* |
| `/comms/` | **Inbox unifié** — Email + Telegram, tri IA (priorité / à répondre) |
| `/observer/` | Vue spectateur live | 
| `/cockpit/` | Workspaces multi-agents |
| `/django-admin/` | Admin |

### Veille éditoriale (`apps/veille`) — chaîne complète communiqué → blog
Pipeline : ingestion IMAP → catégorisation (9 verticales) → **rédaction humanisée dans la plume de
Thérèse** (via le `claude` local, sans clé API) → SEO → images → inter-maillage → calendrier →
publication **en brouillon** vers le MCP de 13 Atmosphère (validation humaine côté blog).

```bash
python manage.py veille_seed              # crée les blogs (principal + catégories)
python manage.py veille_pipeline          # ORCHESTRATION : sync→media→pexels→draft→link→calendar
# …ou étape par étape :
python manage.py veille_sync              # ingestion IMAP (idempotent, HTML→texte, images+PJ+liens)
python manage.py veille_media             # télécharge les images des mails en local
python manage.py veille_pexels            # fallback images libres de droit (Pexels) si visuel manquant
python manage.py veille_draft --limit 10  # rédige (plume de Thérèse) + SEO ; rapporte le coût claude
python manage.py veille_link --all        # inter-maillage : articles liés (backlinks SEO)
python manage.py veille_calendar          # planifie (défaut : semaine +1)
python manage.py veille_export            # export JSON autonome par article (exports/veille/)
python manage.py veille_mcp_ping          # test connexion/sécurité du MCP
python manage.py veille_publish --send    # pousse les brouillons validés vers le MCP (retry/backoff)
```

**Automatisation (cron)** : `*/30 * * * * cd /…/spacelabs && .venv/bin/python manage.py veille_pipeline`.

**Surfaces** : `/veille/` (constellation + calendrier), `/veille/articles/` (list view, filtres,
**pop-up quick view**, panneau **Suivi publication**), `/veille/articles/<id>/edit/` (revue :
photo principale, galerie **drag-n-drop**, suppression d'image, date, contrôle des slugs).

**Rédaction & SEO** : voix décrite dans `apps/veille/plume_therese.md` ; `veille_draft` produit
titre, chapô, corps (rubriques), **seo_title / meta description / tags / alt**, et rapporte le
**coût/tokens** (abonnement Claude Code, pas de facturation API au token).

**Ingestion robuste** : `veille_sync` idempotent (dédup `Message-ID`), fallback **HTML→texte**,
images (`<img>`, liens image, **pièces jointes** locales), liens du mail typés (kit presse
we.tl/Dropbox/Drive), HTML brut conservé (`corps_html`).

**Publication MCP** (draft only — 13-atmosphere seul publicateur) : `apps/veille/mcp.py` mappe nos
articles sur `draft_article` + `set_cover_image` + `add_carousel_images`, avec **retry/backoff** sur
503, **mapping des catégories** (`VEILLE_CATEGORY_MAP`) et **cascade récursive** de la constellation
(pousser un article propose de pousser aussi les liés et les liés des liés). Suivi de l'état
(brouillon/publié) via `list_drafts`. Secrets (`VEILLE_IMAP_*`, `ATMOSPHERE_MCP_TOKEN`,
`PEXELS_API_KEY`) dans `.env.local` (gitignoré).

### Communication unifiée (`apps/comms`)
Boîte de réception névralgique multi-canal + tri automatique (priorité, besoin de réponse).
```bash
python manage.py comms_sync_email     # ingestion IMAP de la boîte
python manage.py comms_sync_telegram  # ingestion DM Telegram (getUpdates)
bash deploy/comms_poll.sh             # suivi constant (boucle détachée)
```
Omnicanal complet (WhatsApp / Instagram DM / SMS) via **Chatwoot** :
`bash deploy/chatwoot/setup.sh` (nécessite Docker).

### Secrets locaux
Jamais commités. Copie `.env.example` → `.env`, et mets les identifiants IMAP/Telegram
dans **`.env.local`** (gitignoré) :
```bash
VEILLE_IMAP_USER=…   VEILLE_IMAP_PASS=…
COMMS_IMAP_USER=…    COMMS_IMAP_PASS=…    COMMS_TG_TOKEN=…
```

## Aucune clé API

SpaceLabs spawne les binaires CLI déjà authentifiés sur **votre** machine
(`claude`, ou toute CLI de votre liste blanche — ex. `openclaw`). Pas
d'intermédiaire, pas de token qui transite : vos abonnements, vos crédits,
vos credentials restent chez vous (`~/.claude`, etc.).

La liste blanche `COCKPIT_ALLOWED_CMDS` décide seul de ce qui est spawnable.

## Démarrer

```bash
make setup    # dépendances + migrations + utilisateur local « pilote »
make redis    # (optionnel en dev) Redis via docker compose
make run      # daphne sur http://127.0.0.1:8000
```

Installation simplifiée (sans `make`) :
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_demo        # crée l'utilisateur « pilote »
python manage.py runserver 0.0.0.0:8000 --settings=config.settings.dev
```
Puis ouvre **http://localhost:8000/dashboard/**.

Connexion : `pilote` / `cockpit-local` (change-le). La page cockpit ouvre un
pane terminal qui lance `COCKPIT_DEFAULT_CMD` dans un vrai PTY — ferme l'onglet,
reviens : la session continue et l'historique est rejoué.

Configuration : copie `.env.example` → `.env`. Variables clés :
`COCKPIT_DEFAULT_CMD`, `COCKPIT_ALLOWED_CMDS`, `COCKPIT_MAX_PANES`,
`COCKPIT_OWNER_MAX_PANES`, `REDIS_URL`, `ALLOWED_HOSTS`.

### Mode « full matrix » (streaming)

Pour suivre 13+ agents simultanément et diffuser l'écran en live :

```bash
# .env
COCKPIT_OWNER_MAX_PANES=16
COCKPIT_OBSERVER_MAX_TILES=16
```

Puis active le mode live et partage `/observer/` — tuiles publiques expurgées,
placeholders pour le privé, bouton panique.

![Observer — vue spectateur temps réel](docs/screenshots/observer_matrix.png)

## Architecture en bref

- **Django 5.2 + Channels/Daphne** — ASGI, WebSockets, SSE
- **PTY noyau maison** — spawn, replay, reprise, kill propre, isolation par utilisateur
- **MTI + registre polymorphe** — `PtyPane` / `HeadlessPane`, dispatch sans `isinstance`
- **Celery** — exploitation depuis la base, source de vérité unique
- **Design system 2 thèmes** — densité assumée, état lisible en périphérie (voir `BRAND.md`)

![Thème clair](docs/screenshots/light_theme.png)

## Sécurité — à lire avant d'exposer quoi que ce soit

Ce cockpit **exécute des process avec vos droits utilisateur** :

- ne l'exposez **jamais** sur Internet — LAN de confiance uniquement ;
- `COCKPIT_ALLOWED_CMDS` est la liste blanche : n'y mettez que des binaires assumés ;
- `--dangerously-skip-permissions` retire les garde-fous de l'agent : choix explicite,
  répertoires maîtrisés (voir `SECURITY.md`) ;
- la vue spectateur est **privée par défaut** : rien ne sort sans activation du mode live.

## État — Sprint 7

Fonctionnalités détaillées dans [`CHANGELOG.md`](CHANGELOG.md), cap dans
[`ROADMAP.md`](ROADMAP.md). Contributions bienvenues — lire
[`CONTRIBUTING.md`](CONTRIBUTING.md) et [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md),
puis ouvrir une issue.

Docs (MkDocs Material) : `pip install mkdocs-material && mkdocs serve`, ou voir
[`docs/`](docs/).

## Licence

MIT — voir [LICENSE](LICENSE).
