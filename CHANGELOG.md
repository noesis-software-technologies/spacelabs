# Changelog

Toutes les évolutions notables. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnage [SemVer](https://semver.org/lang/fr/).

## [Non publié] — Full matrix observateur

### Ajouté

- **`COCKPIT_OBSERVER_MAX_TILES`** : plafond de tuiles de la vue télé `/observer` désormais configurable via l'environnement (défaut inchangé : 9). Le mode « full matrix » monte le plafond (ex. 16) pour suivre tous les agents en parallèle — pensé pour le live streaming (Twitch/Kick).
- `.env.example` documente la nouvelle variable et ajoute `tmux` à la liste blanche d'exemple (`COCKPIT_ALLOWED_CMDS`) pour les panes miroir de sessions de travail.

### Modifié

- `apps/observer/views.py` : la constante codée en dur `OBSERVER_MAX_TILES = 9` devient un réglage lu au rendu (`_observer_max_tiles()`), sans changement du comportement par défaut ni du filtrage public/privé.

## [Non publié] — Sprint 3 (revamp) : presets d'agents configurables

### Ajouté

- **Presets configurables** via `COCKPIT_AGENT_PRESETS` (settings ou JSON d'environnement) : définir ses propres agents (key, label, kind, cmd, color, icon, description) sans toucher au code. Fourni, ce réglage **remplace** la liste intégrée ; vide, les défauts (Claude/Codex/Cursor/Terminal/Chat) s'appliquent. Format documenté en commentaire dans `config/settings/base.py`.
- **Chargeur tolérant + check franc** : `get_agent_presets()` normalise et ignore les entrées invalides (repli sur les défauts si aucune n'est exploitable) ; un nouveau system check (`runtime.E003` / `runtime.W002`) signale une config mal formée avec la raison — mêmes règles des deux côtés.
- Sécurité inchangée : un preset configuré passe toujours par `pane_create` et la liste blanche (`resolve_allowed_binary`) ; un agent configuré mais non autorisé apparaît désactivé.
- **8 tests** : repli / remplacement / validation / rendu.

### Modifié

- `apps/workspaces/agents.py` : liste en dur → `DEFAULT_AGENT_PRESETS` + `get_agent_presets()` piloté par le réglage.

> Reste (hors fork missions→modes) : onglet Browser du dock, ASR streaming, surface Mémoire.


## [Non publié] — Sprint 2 (revamp) : presets d'agents

### Ajouté

- **Presets d'agents** (Claude Code, Codex, Cursor, Terminal, Chat) : un sélecteur « Nouvel agent » (modale `#modal`) remplace les boutons Terminal/Chat. Chaque preset disponible crée un pane via le pipeline `pane_create` existant (`hx-vals`) et s'ajoute à `#pane-grid`.
- **Disponibilité honnête** : un preset pty n'est proposé que si son binaire est dans la liste blanche ET résolu sur l'hôte ; sinon il est affiché **désactivé** avec la raison (« hors liste blanche » ou « introuvable sur l'hôte »). Aucun contournement du durcissement Sprint 17 — `resolve_allowed_binary` s'applique inchangée.
- `apps/workspaces/agents.py` (registre + disponibilité), `templates/workspaces/partials/_agent_picker.html`, vue + route `workspaces:agent_picker`, styles `.agent-*` dans `static/css/shell.css`.
- **5 tests** : logique de disponibilité (liste blanche + PATH), rendu du sélecteur avec cartes désactivées, spawn d'un preset disponible, entrée de toolbar.

### Modifié

- Toolbar et état vide : bouton unique « Nouvel agent » → sélecteur ; raccourcis `n`/`c` et commande de palette repointés vers ce sélecteur.

> Reste (hors fork missions→modes, en pause) : onglet Browser du dock, ASR streaming, surface Mémoire.


## [Non publié] — Sprint 1 (revamp) : palette de commandes ⌘K

### Ajouté

- **Palette de commandes ⌘K** (maquette v2, absente jusqu'ici) : overlay `#palette`, 15 commandes (modes, création de pane, tout lancer, grille dense, direct, panique, régie, onglets du dock, panneaux coulissants). ⌘K/Ctrl+K bascule ; ↑↓/Entrée/Échap ; filtrage au fil de la frappe ; bouton loupe dans la toolbar (`[data-palette-open]`).
- **Lanceur sans logique dupliquée** : chaque commande déclenche un contrôle existant du cockpit ; une commande n'apparaît que si sa cible est présente dans le DOM (palette contextuelle).
- `static/js/palette.js` + styles `.shell-palette` / `.pal*` dans `static/css/shell.css` (portés de la maquette, sur les `--ds-*`) ; overlay + script chargés dans `base.html`.
- **3 tests** : coquille + script servis, déclencheur en toolbar, et présence de **toutes** les cibles déclenchées par la palette.

> Reste (décision produit) : board/swarm/memory en place dans `#stage` (repli de la couche missions), onglet Browser du dock, ASR streaming, surface Mémoire.


## [Non publié] — Sprint 0 (revamp) : recomposition du cockpit mono-écran (Option A)

### Corrigé

- **Créer un terminal écrasait tout le cockpit** : les boutons Terminal/Chat et le formulaire de pane ciblaient `hx-target="#content"`, remplaçant toolbar + grille + dock par un pane nu. Cause : le shell vivait dans `#content`, sans frame persistant. Désormais **aucune action in-cockpit ne vise `#content`** — la création ouvre une modale (`#modal`) et **ajoute** le pane à `#pane-grid` (`beforeend`). Le fragment renvoyé était déjà correct ; seul le ciblage écrasait.

### Ajouté

- **Cockpit recomposé (mono-écran, maquette v2)** : en-tête (`.workspace-toolbar`) / scène (`#stage`) / barre de statut, dock en side panel coulissant. Sélecteur de mode (terminals | board | swarm | memory), crumb, panneaux coulissants (sidebar ⌘B, dock ⌘\), overlay modal.
- `static/css/shell.css` : composition du cockpit + couche d'alias vers les `--ds-*` (mêmes tokens que la maquette) ; ne redéfinit aucun composant existant.
- `static/js/cockpit-shell.js` : cycle de vie de la modale, toggles de panneaux, raccourcis ⌘B/⌘\, miroir de densité en barre de statut. Aucun WebSocket (le temps réel reste dans `shell.js`/`panes.js`).
- **5 tests** verrouillant le contrat de slots : scène/dock/statut présents, créations → `#modal` (jamais `#content`), formulaire → `#pane-grid`, frame persistant conservé, succès inchangé.

### Modifié

- `pane_create` : le formulaire (ouverture ou erreur) reste dans `#modal` (`HX-Retarget`) ; le succès rend le pane et vise `#pane-grid`.
- `_pane_form.html` : carte de modale, au lieu de remplir `#content`.

> Suite (les slots existent déjà) : swap en place de board/swarm/memory dans `#stage`, palette ⌘K, onglet Browser du dock, ASR streaming, surface Mémoire.


## [Non publié] — Sprint 17 : durcissement

### Sécurité

- **La liste blanche des commandes se contournait par un chemin** : `spawn()` comparait `basename(argv[0])`, donc `~/evil/claude`, `./sh` et `/tmp/evil/claude` s'exécutaient. Le nom doit désormais être **nu**, résolu via le PATH ; c'est le chemin résolu qui part à `execve`. (`COCKPIT_LAN_TOKEN` expose ce chemin au réseau local : la faille était atteignable.)
- **La règle existait en double** : `PtyPaneForm.clean_cmd` avait sa propre version (`rsplit("/")`), non durcie — le pane était créé en base et refusé seulement au démarrage. Extraction de `resolve_allowed_binary()`, **une seule règle** partagée.

### Ajouté

- **Contrôles de configuration** (`manage.py check`) : budget mémoire des tampons (`BUFFER_BYTES × MAX_PANES`, avertissement à 64 Mo, erreur à 512 Mo) et refus d'un chemin dans la liste blanche.
- **Mesures de performance** à 16 agents : 3200 diffusions en 4 ms (1,2 µs/trame), linéarité du tampon circulaire, libération mémoire d'un pane mort.

## [Non publié] — Sprint 16 : le Swarm et la vue télé

### Ajouté

- **Vue Swarm** : le DAG de la mission en graphe, lecture seule, rafraîchi toutes les 4 s. `apps/tasker/graph.py` est **pur** — disposition par niveau de dépendance (plus long chemin), donc une colonne = ce qui peut tourner en parallèle. Sortie garantie même sur un cycle ; repli au-delà de 60 nœuds.
- **Vue télé plafonnée à 9 tuiles**, agents qui travaillent d'abord, mention explicite des agents non affichés. Plafond de *lisibilité* : un mur de 16 tuiles ne se lit pas à trois mètres.

### Corrigé

- **La locale cassait le CSS du graphe** : Django localise les nombres, `8.0` devenait `8,0`, et `style="left: 8,0%"` est invalide — tous les nœuds s'empilaient. Formatage déplacé en Python + 3 tests de régression qui relisent le HTML rendu.
- « 3 niveaus » → « 3 niveaux » (`|pluralize:"x"`).

## [Non publié] — Sprint 15 : le dock (Skills + Éditeur)

### Ajouté

- **`apps/skills`** : skills réutilisables, glissables sur un agent. L'application passe par **`registry[pane.kind].dispatch`** (capacité S9) — aucun `if kind ==`. 4 skills intégrées semées au boot.
- **Éditeur de fichiers** (`apps/workspaces/services/files.py`) : arborescence + aperçu texte, confinés au répertoire du workspace. Service **pur**, testé sans Django.
- **Dock à 3 onglets** (Bridge / Skills / Éditeur), `dock.js` (bascule + glisser-déposer), consomme le CSS `explorer*`, `tree-*`, `skill*`, `mdview`.

### Sécurité

- **Fuite trouvée sur serveur réel** : le workspace par défaut ayant `~` pour `cwd`, l'explorateur listait `~/.ssh`. Les clés étaient bloquées, **pas `~/.ssh/config` ni `known_hosts`**. Ajout de `SECRET_DIRS` (`.ssh`, `.gnupg`, `.aws`, `.kube`, `.docker`…) : dossier refusé entier, ni listé ni traversé.
- Confinement par `resolve()` (les liens symboliques sortants sont refusés), refus des `.env*` (sauf `.env.example`), des binaires, troncature à 512 ko.

### Corrigé

- Import `dj_settings` déplacé par erreur au sprint précédent : `NameError` à l'exécution de la vue workspace (3 tests).

## [Non publié] — Sprint 14 : charte de marque SpaceLabs

### Ajouté

- **`BRAND.md`** — la charte fait autorité sur le CSS : positionnement, ton, typographie, couleur (sémantique d'état fixe, identité des agents), densité, géométrie, mouvement, marque, iconographie, tableau **v1 → SpaceLabs**, mode d'emploi pour ajouter une surface.
- **`apps/common/tests/test_brand.py`** — **104 tests** qui défendent la charte : couleurs exactes, zéro couleur en dur hors design system, tout token utilisé défini, toute animation avec variante `prefers-reduced-motion`, nom du produit, aucun emoji.
- `--ds-font-display` + `--ds-display-tracking` ; `.ds-brand-mark--lg` / `--ghost`.

### Modifié

- **Fin de la direction v1 « OpenCockpeet »** : titres Source Serif 4 → **Inter resserré** (10 usages, 4 feuilles) ; thème clair crème chaud → **neutre froid** ; marque chevron de terminal → **hexagone + éclair** ; « le cockpit » → **SpaceLabs** dans toute la copie visible (login, 404, 500).
- `--ds-font-serif` reste déclaré mais n'est plus utilisé (test de non-régression).
- Chemins internes inchangés (`/ws/cockpit/`, `COCKPIT_*`, préfixe `--ds-*`) : renommer de la plomberie invisible est du churn.

### Corrigé

- Glyphe `✕` en dur dans la barre vocale au lieu d'une icône SVG (contraire au §8 de la charte).

## [Non publié] — Sprint 13 : Bridge (commande vocale)

### Ajouté

- **`apps/voice/intents.py`** — routage d'intentions **déterministe** (ADR-4), pur et testable : état, ouvrir *n* agents, planifier/lancer/pauser une mission, ajouter une tâche, densité, panique. Vocabulaire fini et documenté ; une phrase non comprise renvoie la liste de ce que Bridge sait faire.
- **`apps/voice/actions.py`** + endpoint `POST /voice/commande/` : décision → effet, avec tenancy (workspace d'autrui ⇒ 404). La voix respecte les plafonds de capacité comme l'UI.
- **Surface Bridge** dans le dock droit : orbe à états, scène, journal, composeur. Consomme le CSS livré (73 classes `bridge*`/`dock*` orphelines → 9). `bridge.js` : Web Speech si disponible, **saisie texte sinon**.

### Corrigé

- **Réconciliation au boot explicite** (dette signalée 2 sprints) : les tâches d'orchestration en vol d'une génération morte sont libérées par `tasker.reconcile_boot()` branché sur `on_server_boot()`, au lieu d'être récupérées par effet de bord.
- **Pluriels non reconnus** : `\bagent\b` ne matche pas « agents » — « lance deux agents », la phrase la plus naturelle du vocabulaire, tombait en `unknown`.

## [Non publié] — Sprint 12 : le Planner

### Ajouté

- **`apps/tasker/planner.py`** : objectif → DAG de tâches via `claude -p`. `build_prompt` / `parse_plan` / `apply_plan` / `collect_text` sont **purs et testés sans lancer Claude** ; seule `request_plan` est async, avec un `ask` injectable.
- **Validation stricte, refus explicite** : 13 cas de rejet (JSON cassé, clés en double, dépendance inexistante, plan trop gros…) et **détection de cycles** par tri topologique — un DAG cyclique bloquerait le board pour toujours. Aucune création partielle en cas de refus.
- **`Mission.planner_pane`** + **`Pane.is_system`** (migrations `tasker.0002`, `workspaces.0007`) : le planificateur est un pane headless (ADR-2) qui compte dans la capacité mais n'est **ni affiché dans la grille ni éligible à l'exécution**.
- Bouton « Faire planifier » sur le board, message de refus, `COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS`.
- 31 tests S12.

### Corrigé

- **Extraction de la réponse du planificateur** : je lisais `normalized["text"]` alors que `normalize()` produit `{"kind":"assistant","blocks":[{"type":"text","text":…}]}`. Le planificateur aurait **toujours** reçu une réponse vide, y compris avec le vrai Claude. Trouvé sur serveur réel, corrigé, verrouillé par deux tests.

## [Non publié] — Sprint 11 : la boucle d'exécution se referme

### Ajouté

- **`apps/tasker/runner.py`** : la décision devient un **envoi**. `run_once()` tourne dans le processus qui possède les managers, appelle `tick()` puis dispatche via la capacité `dispatch` du registre. Boucle démarrée à la première connexion WebSocket (pas de boucle asyncio à l'import d'`asgi.py`).
- **Détection de fin par signal** : `post_save` sur `EventLog` — un événement `result` clôt la tâche en cours de l'agent avec son coût. Le pipeline runtime ne sait rien de l'orchestration.
- **`reap_stale()`** : libère les tâches dont l'agent est mort ou qui dépassent `COCKPIT_TASKER_TASK_TIMEOUT_SECONDS` (défaut 900 s). La tâche repasse par `fail()` — retentée ou gelée.
- `COCKPIT_TASKER_AUTORUN` (désactivable), `conftest.py` qui coupe la boucle pendant les tests.
- 11 tests S11.

### Notes

- **Ordre des sprints inversé** : le planner IA passe après. Un planner qui écrit des tâches que personne n'exécute n'aurait rien prouvé.
- Scénario live vérifié : agent démarré via le vrai WebSocket → réservation atomique → envoi → clôture par `result` → **mission terminée**, sans intervention.

## [Non publié] — Sprint 10 : Master Tasker (mécanique, sans IA)

### Ajouté

- **`apps/tasker`** : `Mission` / `Task` / `Assignment`, dispatcher **pur DB** (le worker Celery ne voit pas les managers mémoire), résolution du DAG, retries bornés, budget qui met la mission en pause.
- **Assignation atomique** `select_for_update(skip_locked=True)` : deux workers ne peuvent pas donner la même tâche à deux agents.
- **Filtre ADR-1** : seul un type de pane avec `can_autocomplete` est orchestrable — le PTY (ANSI opaque) est exclu, avec un message explicite dans l'UI.
- **Board de mission** (5 colonnes, glisser-déposer htmx) + `static/css/tasker.css`, écrit **intégralement en tokens `--ds-*`** (zéro couleur en dur) + `static/js/board.js` (vanilla, survit aux swaps htmx).
- Battement Celery `tasker.tick_all` (`COCKPIT_TASKER_TICK_SECONDS`, défaut 5 s), lien « Missions » dans la toolbar workspace.
- 23 tests S10.

### Corrigé

- **Commentaires `{# … #}` rendus dans la page** : la syntaxe Django est **mono-ligne uniquement** ; les commentaires multi-lignes que j'avais introduits au sprint précédent s'affichaient à l'écran. Tous supprimés + test de non-régression sur l'ensemble des templates.
- **`fail()` se fiait à un compteur périmé** : l'appelant tient souvent une `Task` chargée avant le claim → une tâche pouvait être retentée au-delà de `max_attempts` (boucle infinie sur un échec systématique). `attempts` est relu en base.
- **Une mission close ne se rouvrait pas** : ajouter une tâche à une mission « terminée » (le cas du replan S11) la laissait fermée avec du travail en attente. Elle repart désormais en `running`.

## [Non publié] — Sprint 9 : fondations « n instances »

### Ajouté

- **`Workspace.max_panes`** (migration 0006) : plafond d'agents simultanés **par workspace**, éditable. Vide = plafond global.
- **`COCKPIT_OWNER_MAX_PANES`** : plafond par compte, distinct du plafond par workspace. Défaut de `COCKPIT_MAX_PANES` porté de 12 à **16**.
- **`apps/runtime/capacity.py`** : décision de capacité **en base** (source vraie cross-process), point d'application unique dans le consumer pour les deux familles.
- **Capacité `dispatch` du registre** + `apps/runtime/dispatch.py` : envoyer une consigne à un pane sans connaître son type (prépare le Master Tasker). `can_autocomplete` porte l'ADR-1.
- 18 tests S9 ; jauge avec niveau visuel (`ok`/`warn`/`full`) ; erreur de capacité remontée en toast.

### Corrigé

- **Plafond global au processus** : deux comptes à 6 panes se bloquaient mutuellement à 12. Compté par propriétaire et par workspace.
- **Chat headless non plafonné** : `HeadlessManager.start()` n'avait aucun contrôle, on pouvait ouvrir n sessions `claude -p`.
- **Jauge mensongère** : elle affichait `actifs / MAX_PANES` en comptant les deux familles alors que le plafond n'en couvrait qu'une. Elle lit désormais la même limite que l'enforcer.
- **Badge trompeur** : « 0/16 agents » à côté de 2 panes visibles → « 2 agents » · « 0/16 en cours ».
- Relancer un pane ne le compte plus lui-même ; un `chat_start` sur session vivante (F5) ne consomme pas de capacité.

### Modifié

- `test_gauges_render` : libellé « Panes actifs » → « Agents en cours » (vocabulaire produit unifié).

## [Non publié] — Passe design system sur les templates + roadmap S9→S16

### Ajouté

- **ROADMAP.md** : chemin complet vers *n instances Claude Code par workspace* + **Master Tasker** (S9 socle → S16 durcissement), avec 6 ADR et les dépendances entre sprints.
- **Segmented controls** (`.ds-seg`) dans la toolbar workspace : densité (4 paliers, `aria-pressed`) et **colonnes** (auto/2→6). Le CSS `.pane-grid[data-cols]` existait sans aucune UI pour le piloter ; les colonnes sont persistées en localStorage.
- **Compteur `n/max` agents** dans la toolbar, **badges d'agents + pastille** par workspace en sidebar, **compteur d'agents** sur la vue télé (`.observer-count`).
- `OwnedQuerySet.with_counts()` — comptes de panes annotés en une requête.

### Corrigé

- **`.ds-gauge` utilisé sans être défini** : le conteneur de jauge n'avait aucun style (ça tenait par le `gap` de `.ds-gauges`).
- **`.pane--zoomed` posé par `grid.js` sans être défini** : en densité `micro`, le pane zoomé restait en 9px alors qu'il occupe tout l'écran. Police confortable + actions toujours visibles.
- **N+1 dans la sidebar** : `ws.panes.first.status` faisait une requête par workspace → 3 requêtes au total désormais.
- **Actions de pane non densité-aware** : les en-têtes utilisaient `.ds-btn--icon` au lieu de `.pane-action`, qui s'efface en `dense`/`micro`. À 16 panes × 7 boutons, les barres de titre saturaient.
- **Action destructive sans affordance au repos** : `.pane-action--close` n'avait qu'un `:hover`.
- **Dérive sémantique en régie** : `.ds-auth-title`/`.ds-auth-sub` (page de connexion) remplacées par `.regie-title`/`.regie-sub` + `.regie-effect`.

### Connu (contenu de S9, non corrigé ici)

- `COCKPIT_MAX_PANES` est **global au processus**, pas par workspace ni par owner : deux utilisateurs à 6 panes bloquent tout le monde.
- `HeadlessManager.start()` **n'applique aucun cap** ; la jauge affiche pourtant `actifs / MAX_PANES` en mélangeant PTY et headless — elle ment.
- Le registre polymorphe n'a **pas de capacité `dispatch`** : sans elle, tout orchestrateur finira en `if pane.kind == …`.

## [Non publié] — Sprints 7 → 8

### Modifié

- **Rebranding SpaceLabs** : OpenCockpeet → SpaceLabs partout (marque, loggers, Celery, clés localStorage, docs). Chemins internes conservés.
- **Design system adopté** (fourni) : accent orange #f77615, fonds noir profond, tokens densité/agents/Bridge ajoutés. Mêmes noms de classes.

### Ajouté

- **Échelle de densité** cozy/compact/dense/micro : bouton de cycle persisté + xterm câblé sur --ds-pane-fs (panes.js) pour que 16 panes tiennent lisiblement à l'écran.

### Corrigé

- **Dashboard inutilisable en navigation SPA** : `terminal.css`, `panes.js` et `chat.js` vivaient dans des blocs `<head>` que htmx ne recharge pas sur un swap `#content` → workspace sans styles/terminaux/chat/zoom après navigation sidebar. Assets désormais chargés globalement dans le shell.
- **Zoom de pane** : sortie de la dépendance Alpine (fragile après swap htmx), réécrite en vanilla par délégation (`grid.js`) + réagencement `data-count`. Script Alpine retiré. Commentaires `{# #}` supprimés des templates.

### Corrigé

- **Portabilité Windows** : l'app crashait à l'import sur Windows (`ptyprocess`→`fcntl`, Unix-only). Backend PTY multiplateforme à import différé (ptyprocess/POSIX, pywinpty/Windows), marqueurs de plateforme dans `requirements.txt`. Chemin POSIX inchangé ; WSL2 recommandé pour Windows.

### Ajouté

- **Reprise headless fidèle** (S8) : l'identifiant de session Claude est
  persisté ; après un redémarrage, un chat reprend **exactement** la même
  conversation via `claude -p --resume <id>` (au lieu de `--continue`). Envoyer
  un message dans un pane connu continue sa conversation ; un bouton « nouvelle
  conversation » repart à neuf.

- **Voix serveur verbatim** : backend **CrisperWhisper** (faster-whisper /
  CTranslate2) en plus de la Web Speech API. Bascule par `COCKPIT_STT_BACKEND` ;
  en mode serveur le navigateur capture l'audio (MediaRecorder) et le serveur
  transcrit (fillers, hésitations inclus) — offline, rien ne sort de la machine.
  Transcripteur pluggable + factice pour les tests (le vrai modèle n'est pas
  téléchargeable en CI).

## [0.1.0] — Sprints 1 → 6

Première version publiable : cockpit web local-first pour Claude Code.

### Ajouté

- **Fondations & noyau PTY** (S1) : ASGI/Daphne dès J0, utilisateur custom,
  `PaneManager` (spawn PTY, ring buffer de replay, diffusion WebSocket par
  groupe Redis, liste blanche de commandes, isolation par propriétaire),
  shell persistant et design-system (deux thèmes, anneau de statut).
- **Workspaces & panes polymorphes** (S2) : modèle `Pane` en MTI + registre,
  CRUD htmx, grille avec splits/zoom (Alpine), protocole WebSocket par pk de
  pane persistant, replay/resync après F5.
- **Observateur & confidentialité** (S3) : vue SSE anonyme plein écran,
  règles de redaction côté serveur, **privé par défaut**, mode direct,
  bouton panique. Invariants : rien ne fuit tant que le direct est coupé ou
  le pane privé ; passer public ne révèle pas le passé.
- **Chat headless** (S4) : `claude -p --output-format stream-json`
  bidirectionnel, parsing/normalisation d'événements, **`EventLog`
  (persistance intégrale)**, rendu chat (bulles, outils repliables,
  coût/durée), boutons d'amorce, **même pipeline public/privé** que le PTY.
- **Exploitation** (S5) : Celery + beat (instantanés d'usage → jauges de la
  sidebar, faucheur de zombies par génération/heartbeat cross-process,
  purge/archivage d'`EventLog`, détection MCP → bouton `/mcp`), raccourcis
  clavier, **réconciliation au démarrage** (indépendante du serveur).
- **Voix & publication** (S6) : **push-to-talk** par pane (Web Speech API
  `fr-FR`, transcript éditable, envoi en stdin pour le PTY / composer pour le
  chat), **garde par jeton LAN** optionnelle, **reprise de session au boot**
  optionnelle (bouton + reprise auto), documentation de publication.

### Sécurité

- Redaction côté serveur (bytes→bytes) partagée PTY/chat ; buffers publics
  purgés à la coupure du direct ou au passage en privé.
- Mode headless autonome désactivé par défaut ; jeton LAN pour l'exposition
  réseau ; `pip-audit` : aucune vulnérabilité connue sur les dépendances.

### Limites connues

- Continuation d'un chat headless après redémarrage complet : best-effort via
  `--continue` (la reprise par `--resume <session_id>` nécessiterait de
  persister l'identifiant de session — évolution prévue).
- Sémantique du coût d'usage : suppose `total_cost_usd` cumulatif par session.
- Détection MCP : heuristique par motifs configurables.

## [Non versionné] — 2026-08-26 · PR1+PR2 du backlog (fix main + CI)
- fix(tests): `test_observer_caps_tiles_and_says_how_many_are_hidden` lit le
  plafond effectif via `_observer_max_tiles()` au lieu de la constante
  `OBSERVER_MAX_TILES`, volontairement supprimée par le commit full-matrix
  (plafond configurable `COCKPIT_OBSERVER_MAX_TILES`). Main : 524/524 vert.
- ci: workflow GitHub Actions (`.github/workflows/ci.yml`) — check Django +
  pytest sur push/PR, Python 3.12, sans faster-whisper (optionnel, lourd),
  sans Redis (dev = SQLite + InMemoryChannelLayer).

## [Non versionné] — 2026-08-26 · S-R1 MODEL_ROUTING (ADR-5, socle)
- feat(models_routing): nouvelle app — backends (claude_bin / openai_http),
  règles de routage ordonnées, budgets de tokens par mission, RunLog ;
  admin + migration + fixture `routing_defaults` (table de la spec §6).
- feat(models_routing): OpenAIHttpAdapter (httpx SSE, pré-vol overflow,
  usage réel via stream_options) + commande `backends_health`.
- sec: base_url restreinte au LAN/loopback (validation IP privée, spec §8).
- fix(router): incréments de budget via F() — atomiques, pas de
  lire-modifier-écrire (deux runs simultanés ne s'écrasent plus).
- deps: httpx ajouté aux requirements.

## [Non versionné] — 2026-08-26 · S-R2 MODEL_ROUTING (exécution routée)
- feat(tasker): champ Mission.task_class (D2) — la classe déclarée que lit le routeur.
- feat(models_routing): ClaudeBinAdapter one-shot — même argv/protocole que
  HeadlessManager, parsing réutilisé (apps.chat.events) ; les sessions longues
  des panes restent au HeadlessManager.
- feat(models_routing): RunLogger — un JSONL append-only par run (var/runs/),
  deltas échantillonnés (compteur, pas de payloads — spec §8), RunLog finalisé
  (statut, tokens, durée).
- feat(models_routing): execute_routed_run — route() → adapter → JSONL →
  diffusion chat.event sur pane_{id} : le CockpitConsumer et le front
  existants affichent les runs routés sans modification.
- budgets : consommation créditée sur l'usage RÉEL (pas l'estimation) ;
  un run en erreur ne consomme pas.

## [Non versionné] — 2026-08-26 · S-R3 MODEL_ROUTING (UI + calibration)
- feat(ui): segment routeur dans la statusbar du cockpit (backend du dernier
  run + budget mission, poll htmx 4 s, auto-swap — aucune cible #content) ;
  panneau « Runs routés » dans la régie (backend, classe, tokens, durée,
  chemin JSONL, poll 8 s).
- feat(models_routing): commande `calibrate_thresholds` — sonde le backend
  local, mesure pp/gen tok/s (TTFT), applique la règle du budget temps de la
  spec §6 et cale max_est_tokens sur les règles qui en portent. Les seuils
  provisoires de la fixture deviennent des valeurs MESURÉES sur la machine.
- chore: var/ ignoré (journaux de runs hors repo).
