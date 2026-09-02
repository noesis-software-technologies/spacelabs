# CLAUDE.md — SpaceLabs

Cockpit web local-first (Django) qui pilote des sessions Claude Code / shells
dans des PTY, streamées en WebSocket vers des panes xterm.js. Réfère-toi au
cahier des charges (CDC) pour la vision complète et au Blueprint v3.1 Noélabs
pour les invariants — ils priment sur toute habitude.

## Commandes

- `make setup` · `make run` (daphne :8000) · `make redis` · `make check` · `make test`
- Tests : `python -m pytest -q` (asyncio_mode=auto, settings dev, PTY réels)
- Prod locale : `DJANGO_SETTINGS_MODULE=config.settings.prod` + `SECRET_KEY` requis

## Portabilité (Windows)

- `apps/runtime/services/pty_backend.py` : abstraction PTY, import de la lib
  différé dans `spawn` (l'app démarre sur Windows sans ptyprocess). POSIX =
  ptyprocess (fd + add_reader, inchangé) ; Windows = pywinpty (thread lecteur,
  terminate() au lieu de SIGKILL). `pane_manager` branche selon `handle.uses_fd`.
- requirements : ptyprocess (sys_platform != win32) / pywinpty (== win32).
- Support pleinement vérifié : POSIX (Linux/macOS) et **WSL2**. Windows natif :
  boot + fonctions hors-PTY OK ; PTY pywinpty best-effort (non vérifié en CI).

## Architecture (Sprint 9)

- `apps/runtime/capacity.py` — **la décision de capacité se prend en BASE**
  (comme `apps/ops/services.py`) : seule source vraie cross-process. Plafond
  **par workspace** (`Workspace.max_panes`, vide = `COCKPIT_MAX_PANES`) ET
  **par compte** (`COCKPIT_OWNER_MAX_PANES`, 0 = même valeur). Point
  d'application unique : `_check_capacity()` dans le consumer, appelé pour le
  PTY **et** le headless. Les managers gardent un garde-fou mémoire *par
  propriétaire* (défense en profondeur) — avant S9 il était global et deux
  comptes se bloquaient mutuellement.
- Comptage : panes **RUNNING en base**, tous types confondus (un agent est un
  agent). `exclude_pk` pour qu'un pane qui redémarre ne se compte pas lui-même ;
  un `chat_start` sur session vivante (F5) ne consomme pas de capacité.
- `apps/runtime/dispatch.py` + **capacités du registre** : `dispatch_path`
  (résolu paresseusement — sinon cycle `models → runtime → models`) et
  `can_autocomplete`. Envoyer une consigne à un pane **sans tester son kind**
  (§6.9). `can_autocomplete` : headless=True (événement `result` exploitable),
  pty=False (ANSI opaque, invariant n°1) — c'est l'ADR-1 rendu exécutable.
- Jauge : lit `owner_limit()`, la **même** limite que l'enforcer (elle affichait
  auparavant un plafond qui ne s'appliquait qu'aux PTY).

## Architecture (Sprint 8)

- Reprise headless fidèle : `HeadlessPane.claude_session_id` persisté à l'init
  (dans `_read_loop`). `HeadlessManager._build_argv(resume, resume_session_id)`
  → `--resume <id>` / `--continue` / rien ; `start(resume_session_id=…)`.
- Consumer : `chat_start(resume)` passe l'id stocké ; `chat_send` continue une
  conversation connue (reprise implicite) ; `chat_reset` coupe + oublie l'id
  (nouvelle conversation / échappatoire session expirée).
- UI : bouton ↺ « nouvelle conversation » sur le pane chat (chat.js → chat_reset,
  vide le transcript à l'ack).
- Test infra : fake_claude journalise ses argv si FAKE_CLAUDE_ARGV_LOG est défini
  (le smoke prouve que --resume <id> atteint le binaire).

## Architecture (Sprint 7)

- `apps/voice` — reconnaissance vocale serveur (sans modèle DB). `backends.py` :
  factory `get_transcriber()` sur COCKPIT_STT_BACKEND → `CrisperWhisperBackend`
  (faster-whisper + CTranslate2 `nyralabs/faster_CrisperWhisper`, modèle chargé
  paresseusement, décodage ffmpeg → WAV 16k mono) / `FakeTranscriber` (tests) /
  None si `webspeech`. `views.py` : POST /voice/transcribe/ (login, champ audio,
  25 Mo) → {text}.
- Front : `voice.js` généralisé — body[data-stt-backend] choisit Web Speech
  (navigateur, S6) ou capture MediaRecorder → upload → transcript (serveur).
  Mêmes cibles (composer chat / stdin PTY), transcript éditable.
- Réglages COCKPIT_STT_* ; backend exposé au client via context processor
  cockpit_flags → body[data-stt-backend, data-transcribe-url]. faster-whisper =
  dépendance optionnelle (prod), non requise pour les tests (backend factice).

## Architecture (Sprint 6)

- Voix : `static/js/voice.js` — push-to-talk Web Speech API fr-FR par pane
  (micro dans le composer chat ; barre de dictée → stdin pour le PTY),
  dégradation gracieuse. Boutons `[data-voice="chat"|"pty"]`, barre
  `[data-voice-bar]`.
- Accès LAN : `apps/common/middleware.LanTokenMiddleware` (COCKPIT_LAN_TOKEN,
  exempte /healthz + statiques). Enregistré après WhiteNoise.
- Reprise : `Pane.resume_pending` (posé par `reconcile_boot` si
  COCKPIT_RESUME_ON_BOOT, nettoyé par `_stamp_running`), `static/js/resume.js`
  (bouton + reprise auto sur `cockpit:open`), context processor
  `cockpit_flags` → `body[data-resume-on-boot]`. HeadlessManager.start(resume)
  → `--continue`.
- Consumer : op `attach` désormais agnostique du type (dispatche un headless
  vers `chat_attach`) — corrige la ré-attache de shell.js à la reconnexion.
- Publication : CONTRIBUTING.md, CHANGELOG.md, SECURITY.md.

## Architecture (Sprint 5)

- `apps/ops` — exploitation. `models.py` (UsageSnapshot, RuntimeHeartbeat,
  MCPAlert), `services.py` (fonctions PURES DB-only : usage_for_owner,
  external_usage, snapshot_all_owners, reconcile_boot, reap_zombies,
  archive_eventlog, scan_mcp_auth), `tasks.py` (4 @shared_task ops.*),
  `views.py` (gauges + resolve_mcp), commande reconcile_panes.
- Cross-process : le worker Celery ne voit PAS les managers en mémoire → tout
  passe par la DB. Zombies détectés par génération : `runtime_state.BOOT_ID`
  (uuid/processus) estampillé au spawn (`Pane.runtime_boot_id`), + heartbeat DB
  (RuntimeHeartbeat) pour savoir si Daphne vit. Pas de scan PID.
- Boot : `startup.on_server_boot()` appelé à l'import de `config/asgi.py`
  (indépendant du serveur ; Daphne n'émet pas lifespan de façon fiable) —
  réconcilie + lance un thread daemon de battement. `lifespan.LifespanApp`
  minimal pour arrêt propre (uvicorn).
- Celery : `CELERY_BEAT_SCHEDULE` statique (snapshot 60s, reap 120s, scan MCP
  120s, archive 3600s). `make worker` / `make beat`.
- Front : jauges sidebar (polling htmx 30s), bouton /mcp sur chat en alerte,
  `static/js/shortcuts.js` (raccourcis + overlay d'aide).

## Architecture (Sprint 4)

- `apps/chat` — `EventLog` (persistance intégrale : FK Pane, seq unique/pane,
  origin raw|user, payload brut + normalized), `events.py` (parse_line /
  normalize / user_event / redact_event), `tests/support/fake_claude.py`
  (faux binaire stream-json pour tests/smoke sans le vrai claude).
- `apps/runtime/services/headless_manager.py` — `HeadlessManager` singleton,
  `HeadlessSession` (subprocess asyncio, pas PTY). start/send/kill,
  `_read_loop` (readline→parse→normalize→persist EventLog→diffuse),
  `_emit` (privé sur pane_{id} + public expurgé sur observer, gaté par
  `PaneManager.live_by_owner`). Pipeline unique §2.13 partagé avec le PTY.
- Consumer : ops `chat_start`/`chat_attach` (replay EventLog durable)/
  `chat_send`/`chat_kill` ; `set_visibility` et `panic` généralisés à tous les
  types (chargement via `_load_base_pane`). Handlers channel layer
  `chat_event`/`chat_status`.
- Settings : `COCKPIT_CLAUDE_BIN` (défaut "claude"),
  `COCKPIT_CLAUDE_HEADLESS_ARGS`, `COCKPIT_PRIMING_PROMPTS` (Build/Plan/Fix).
- Front : `static/js/chat.js` (montage [data-chat-host], bulles, outils
  repliables, coût/durée, primers), `_pane_headless.html` (mêmes contrôles que
  le PTY). Observateur : chats publics en transcript expurgé (event SSE `chat`).

## Architecture (Sprint 3)

- `apps/observer` — `ObserverSettings` (live par owner), `RedactionRule`,
  `redaction.py` (compile_redactor bytes→bytes). Vues : `/observer/` page télé
  anonyme, `/observer/grille/` fragment public filtré par
  `_public_grid_context()` (SEUL chemin de filtrage), `/observer/stream/` SSE
  async (abonnement channel layer, replay public, keepalive), régie
  (`/observer/regie/`) avec CRUD règles en vues async (refresh runtime direct).
- PaneManager : `buffer_public` expurgé par pane, `live_by_owner`,
  `set_live/set_visibility/refresh_redactor/replay_public`,
  `OBSERVER_GROUP="observer_stream"`. INVARIANTS PRIVACY : privé par défaut ;
  live OFF ⇒ zéro trame ; passage public ne révèle pas le passé ; passage
  privé/coupure live purge le buffer public ; replay_public ne touche JAMAIS
  le buffer privé.
- Consumer : ops `set_visibility`, `set_live`, `panic` (live OFF + tout privé,
  DB + runtime). Acks sans pane_id routés vers `CockpitSocket.onGlobal`.
- UI cockpit : œil par pane + badge PUBLIC, boutons live/panique/régie dans
  la toolbar workspace.

## Architecture (Sprint 2)

- `apps/workspaces` — modèles `Workspace` + `Pane` MTI (`PtyPane`,
  `HeadlessPane` S4) ; **registre polymorphe** dans `models.py`
  (`registry`, `register()`, `form_for`, `concrete_panes` anti-N+1) :
  ajouter un type de pane = modèle + form + partial + 1 ligne de registre,
  zéro modif du pipeline. Labels d'agents auto (`AGENT_NAMES`). Tenancy :
  TOUJOURS `for_owner(user)`, objet étranger ⇒ 404.
- Vues workspaces : CRUD double représentation, sidebar dynamique
  (`{% workspaces_sidebar %}` + refresh `HX-Trigger workspacesChanged`),
  création de pane par kind (`pane_create`) qui renvoie le partial du pane.
- Protocole WS (S2) : les panes existent en DB avant le spawn — ops
  `spawn/attach/stdin/resize/kill` par `pane_id` = pk. `spawn` sur un pane
  vivant ⇒ attach+replay (pas de double process). Attach d'un pane
  « running » en DB mais absent du runtime (restart serveur) ⇒ resync dead,
  l'UI propose ↻ (`respawn_cmd()` ajoute `--continue` pour claude).
- `static/js/panes.js` remplace terminal.js : montage par `[data-pane-host]`
  (data-pane-id/status), spawn/attach selon statut, ↻, « Tout lancer ».

## Architecture (Sprint 1)

- `config/` — settings {base,dev,prod} pilotés par env (django-environ),
  `asgi.py` = ProtocolTypeRouter + AuthMiddlewareStack + AllowedHostsOriginValidator.
- `apps/comptes` — User custom (`AUTH_USER_MODEL=comptes.User`), commande
  `bootstrap_demo` (pilote/cockpit-local, idempotente).
- `apps/common/htmx.py` — `render_htmx(request, page, partial, ctx)` : LE
  helper des deux représentations ; il pose aussi `Vary: HX-Request`
  (django-htmx ne le fait pas).
- `apps/runtime/services/pane_manager.py` — singleton asyncio : spawn PTY
  (ptyprocess), lecture via `loop.add_reader` (jamais de thread bloquant),
  ring buffer `COCKPIT_BUFFER_BYTES`, fan-out channel layer groupe
  `pane_{id}`, kill SIGTERM→SIGKILL sans orphelin, liste blanche
  `COCKPIT_ALLOWED_CMDS`, cap `COCKPIT_MAX_PANES`, isolation `owner_id`.
- `apps/runtime/consumers.py` — `CockpitConsumer` : un WS par client,
  multiplexé par `pane_id`. Ops C→S : spawn / attach / stdin / resize / kill.
  S→C : spawned / stdout (base64) / status / error. Auth obligatoire
  (close 4401 → reject 403 au handshake sous daphne), autorisation owner
  AVANT tout `group_add`, stdin base64 validé et plafonné (8 Ko).
- Front : shell persistant `templates/base.html` (sidebar/topbar/toasts/#content),
  `static/js/shell.js` = singletons (thème, toasts, `CockpitSocket` avec
  reconnexion exponentielle + re-attach auto), `static/js/terminal.js` =
  montage xterm par MutationObserver sur `[data-pane-host]`, actions par
  délégation. Tokens dans `static/css/design-system.css` (`--ds-*`, HSL).

## Invariants à ne pas casser

1. La sortie PTY transite en **base64** de bout en bout — ne jamais décoder
   côté serveur (l'ANSI coupe l'UTF-8), ne jamais parser le flux pour en
   extraire du sens métier.
2. Un pane **survit à la déconnexion** ; `attach` rejoue le ring buffer puis
   renvoie le statut. Toute évolution doit préserver ce contrat.
3. Autorisation objet avant `group_add` ; aucun secret ni PII dans les logs.
4. htmx = CRUD/nav (page ↔ partial via `render_htmx`) ; WS = flux runtime
   uniquement ; Alpine = état UI local. Pas de JS inline, config par
   data-attributes, vendors self-hostés (pas de CDN).
5. Ne PAS appeler `Alpine.initTree` dans `htmx.onLoad` : Alpine 3 observe
   déjà le DOM — double init sinon.
6. `config/urls.py` : la debug toolbar se monte sur
   `"debug_toolbar" in settings.INSTALLED_APPS`, jamais sur l'importabilité.
7. Django tourne **sur l'hôte** (accès `~/.claude` + repos) ; seul Redis est
   dockerisé.

## Pièges rencontrés (ne pas re-payer)

- `check --deploy` doit être vert sur `config.settings.prod` (CI du rituel).
- Sous daphne, `close(4401)` avant `accept()` devient un reject HTTP 403 :
  les deux formes sont « anonyme refusé ».
- Les tests PaneManager utilisent de vrais `sh` : toujours tuer les panes en
  fin de test (`reset_for_tests` + kill), vérifier zéro orphelin.

## Roadmap

**Voir `ROADMAP.md`** — cible : *n* instances Claude Code par workspace pilotées
par un **Master Tasker**. Sprints S9 (socle : cap par workspace + capacité
`dispatch` du registre) → S10 (tasker mécanique, sans IA) → S11 (planner)
→ S12 (fiabilité) → S13 (Bridge/voix streaming) → S14 (dock/skills)
→ S15 (swarm + vue télé) → S16 (durcissement).

Décisions structurantes (détail et justification dans `ROADMAP.md` §6) :
ADR-1 les tâches auto-pilotées tournent sur des panes **headless** (le PTY n'a
pas de signal de fin exploitable sans violer l'invariant n°1) · ADR-2 le planner
est un pane headless comme les autres · ADR-3 le dispatcher est un service pur
DB + Celery · ADR-4 le routage d'intentions vocales est déterministe · ADR-5
`dispatch` est une capacité du registre, jamais un `if kind ==` · ADR-6 mode
manuel par défaut, budget obligatoire en auto.

### Historique

S2 workspaces & grille multi-panes (modèles Workspace/Pane MTI) · S3 fan-out
observateur SSE + confidentialité (RedactionRules, liste blanche, mode live,
bouton panique) · S4 chat headless `claude -p --output-format stream-json` +
EventLog · S5 Celery + jauges usage + MCP helper · S6 voix + publication ·
S7 STT serveur (CrisperWhisper) · S8 reprise headless fidèle (`--resume`).

## Harnais de release (toutes équipes, humaines et IA)

Le dépôt est conduit par le harnais de release (`docs/process/HARNESS.md`) : Épic approuvé → terrain
(`scripts/gh/10-new-epic.sh`, 1er commit = feature flag OFF) → `sub-feature/<epic>/<task>` → PR vers
`feature/<epic>` (checklist + QA signée) → PR d'intégration vers `main` (Go/No-Go `scripts/gh/32-go-no-go.sh`,
puis `po-approved`) → tag (`40-release.sh`) → paliers de rollout (`35-rollout.sh`). Règles non négociables :
jamais de push direct sur `main`, pas de merge sans checklist cochée, tout code nouveau derrière un flag
déclaré dans `config/feature_flags.yml`, une équipe ne pousse jamais sur la branche d'une autre
(protocole complet : `docs/process/AI_TEAMS.md`). Vérifier le harnais : `make -f harness.mk verify`.
