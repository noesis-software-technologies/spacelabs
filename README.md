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

### Veille éditoriale (`apps/veille`)
Ingestion des communiqués de presse (IMAP), catégorisation en 9 verticales, dispatch vers le blog cible.
```bash
python manage.py veille_seed    # crée les blogs (principal 13-atmosphere.com + catégories)
python manage.py veille_sync    # ingère + catégorise + dispatche
python manage.py veille_draft --limit 1   # pré-rédige un article dans la plume de Thérèse (via le claude local)
python manage.py veille_media             # télécharge en local les images (ref + galerie) des communiqués
python manage.py veille_link --all        # inter-maillage : articles liés (SEO + navigation)
python manage.py veille_calendar --per-week 3   # planifie les dates de publication des brouillons prêts
python manage.py veille_export --status valide  # exporte les articles en JSON (prêt pour publication via MCP)
```
`veille_draft` génère aussi le **SEO** (titre optimisé, meta description, tags, alt).
`veille_sync` est **idempotent** (dédup par `Message-ID`) et **robuste** : fallback **HTML→texte**
(les communiqués sont souvent HTML-only), extraction des **images** (`<img>`, liens image,
**pièces jointes** sauvées en local) et des **liens** du mail (kit presse we.tl/Dropbox/Drive
détectés), HTML brut conservé (`corps_html`, ré-extractible). Relancer le sync **complète** les
communiqués existants sans doublon. Export MCP : un JSON autonome par article dans `exports/veille/`
(titre, slug, meta, tags, image de référence locale, galerie, corps, liens internes + liens sources).

> Les images/contenus proviennent des mails : il faut **relancer `veille_sync`** (creds IMAP dans
> `.env.local`) pour rapatrier le contenu — les items ingérés avant cette version n'ont pas de corps.
Pré-rédaction humanisée : la voix éditoriale est décrite dans `apps/veille/plume_therese.md`
et injectée dans le prompt ; la génération s'appuie sur le binaire `claude` local (aucune clé API).
Les brouillons (`draft_statut` : brouillon → validé → publié) et le **calendrier de publication**
apparaissent dans `/veille/` et l'admin.

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
