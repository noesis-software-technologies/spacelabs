# Contribuer à SpaceLabs

Merci de ton intérêt ! SpaceLabs est un cockpit web local-first qui pilote
des sessions **Claude Code** (via ton abonnement, sans API) — multi-workspaces,
multi-panes, avec une vue « télé » anonymisée pour tes lives.

## Démarrer en local

```bash
git clone <repo> && cd spacelabs
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # ajuste si besoin (localhost fonctionne tel quel)
python manage.py migrate
python manage.py bootstrap_demo # crée l'utilisateur "pilote" / "cockpit-local"
make run                        # daphne sur http://127.0.0.1:8000
```

Le temps réel (WebSocket/SSE) tourne dès le départ sur ASGI/Daphne. Redis n'est
requis qu'en prod (channel layer) et pour Celery :

```bash
make redis     # Redis via docker compose
make worker    # tâches d'exploitation
make beat      # planificateur
```

> Le cockpit doit tourner **sur la machine où tu es loggé à Claude Code** : on
> spawn le binaire `claude` (auth OAuth `~/.claude`). La « télé » n'est qu'un
> navigateur sur ton LAN pointant vers `/observer/`.

## Lancer les tests

```bash
make test              # pytest (unitaires + consumers ASGI + services)
make check             # migrations à jour + check Django + pytest
```

La suite tourne **sans le vrai binaire `claude`** : un faux binaire stream-json
(`apps/chat/tests/support/fake_claude.py`) reproduit le protocole. En prod, on
pointe `COCKPIT_CLAUDE_BIN=claude`.

## Architecture (pour s'y retrouver)

- `apps/comptes` — utilisateur, bootstrap démo.
- `apps/common` — helpers htmx, middleware (token LAN), context processors.
- `apps/runtime` — cœur temps réel : `PaneManager` (PTY), `HeadlessManager`
  (chat `claude -p` stream-json), le consumer WebSocket unique, le lifespan et
  l'amorçage au boot (`startup.py`).
- `apps/workspaces` — modèle `Pane` polymorphe (MTI) + registre des types, CRUD.
- `apps/observer` — vue SSE anonyme + pipeline de confidentialité (redaction).
- `apps/chat` — `EventLog` (persistance intégrale) + parsing d'événements.
- `apps/ops` — exploitation : Celery (jauges d'usage, faucheur, archivage,
  détection MCP), réconciliation.

Deux documents suivent le fond : `CLAUDE.md` (carte d'architecture vivante) et
`AUDIT.md` (journal des sprints, décisions et preuves de vérification).

### Ajouter un type de pane

Le modèle `Pane` est polymorphe (multi-table inheritance) avec un **registre**
(`apps/workspaces/registry`). Un nouveau type = une sous-classe de `Pane`, une
entrée au registre (label, partial, formulaire) et un runtime si besoin. Le
pipeline public/privé et l'UI de base sont hérités — pas de modification du
noyau.

## Style & conventions

- Frontières nettes : **htmx** = CRUD/navigation, **WebSocket** = flux runtime,
  **Alpine** = état UI local, **SSE** = observateur anonyme read-only.
- Pas de framework JS lourd : vanilla + Alpine, CSS avec tokens `--ds-*`.
- Français pour l'UI et les commentaires (public visé).
- Toute nouvelle logique runtime vient avec ses tests (pytest + communicator
  ASGI). Les smokes Daphne réels valident le bout-en-bout.

## Sécurité

Voir `SECURITY.md`. En résumé : privé par défaut, redaction côté serveur, et le
mode headless autonome (`--dangerously-skip-permissions`) est un choix explicite.
