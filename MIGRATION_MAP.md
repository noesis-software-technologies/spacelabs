# MIGRATION_MAP.md — `spacelabs-demo.html` (nouvelle vision) → kit legacy

**Mesuré sur le zip, fichier par fichier — pas déclaré.** Kit lu à l'état
« 14 » (post-S16, durci S17, `495 passed`, `manage.py check` + `check --deploy`
à 0 issue). La démo Alpine a été lue en entier (composant `bs()`, ~1928 l.).

---

## 0. Correction de mon analyse précédente

Au premier tour, sans le zip, j'ai supposé deux choses. **Les deux sont fausses**,
et je le note comme l'exige la discipline du projet :

1. « Il faut bâtir le transport temps réel (Channels/WS) ». **Non** — il existe
   déjà : `CockpitConsumer` (`apps/runtime/consumers.py`, `ws/cockpit/`) streame
   les PTY xterm et le chat headless. Le morceau le plus dur de la démo est livré.
2. « Il faut trancher Alpine vs htmx ». **Non** — c'est tranché. Le kit est
   **htmx + JS vanilla + xterm.js**, les assets sont chargés **globalement** dans
   `base.html` (donc le bug de swap `#content` sous `<head>` qu'on connaît est
   déjà résolu). Porter l'Alpine de la démo *vers* ce socle, ce n'est pas un choix
   de framework, c'est de la décomposition.

## 1. Recadrage de la prémisse

« L'équipe legacy n'a pas su implémenter cette version. » Le code raconte autre
chose. Le kit est mature (S9→S17, ADR documentés, 495 tests, sprint de
durcissement sécurité complet). Surtout, `ROADMAP.md §7` pose une **décision
assumée**, pas un oubli :

> *« Pas de reproduction de la maquette à l'identique : Board/Swarm/Bridge sont
> repris, mais la maquette simule ses agents ; ici ils sont réels, donc les
> états intermédiaires (assignation, retry, budget) existent et doivent être
> montrés. »*

Autrement dit : la démo **triche** (toutes ses « live » sont des timelines
`setTimeout`), le kit **ne triche pas** (agents réels, donc états réels à
afficher). L'écart entre les deux est un choix de produit documenté. La vraie
question n'est donc pas « rattraper un retard » mais **« converge-t-on l'IA du
kit vers celle de la maquette, ou greffe-t-on les surfaces qui manquent sur
l'IA actuelle ? »** — §5. Je ne tranche pas ça à ta place.

---

## 2. Map des partials : maquette → kit

| Partial maquette | État Alpine | Existe dans le kit ? | Preuve | État |
|---|---|---|---|---|
| Title bar (feux, hexagone, crumb, view-menu, notif, reset) | `mode`, `showModeMenu/Notif` | Chrome **différent** : `ds-sidebar` (gauche) + `ds-topbar` (thème/user) | `templates/base.html` | 🟡 divergent |
| Workspaces panel + badges + mode-switcher | `workspaces[]`, `activeWs` | Sidebar workspaces oui ; **switcher de modes non** | `{% workspaces_sidebar %}`, `_sidebar_list.html` | 🟡 partiel |
| Terminals grid (splash→run, lignes typées) | `terminals[]`, `gridCols` | **Réel** : xterm sur PTY, pas des `lines` factices | `_pane_pty.html`, `panes.js`, `pane_manager.py` | ✅ (supérieur) |
| Densité + colonnes | `density`, `gridMode` | **Réel** | `_workspace_view.html` (`data-density-set`, `data-cols-set`), `grid.js` | ✅ |
| Board (kanban DnD → dispatch) | `board[]` | **Réel** | `templates/tasker/partials/_board.html`, `board.js`, `tasker/runner.py` | ✅ |
| Swarm (graphe de nœuds + progress) | `swarm{}` | **Réel mais autre sémantique** : nœuds = **tâches** d'un DAG (pas rôles agents), poll htmx 4s (pas push WS) | `_swarm.html`, `tasker/graph.py`, `test_swarm_s16.py` | 🟡 divergent |
| Memory (`.bridgememory` note-graph) | `memGraph`, `memNotes` | **Absent** comme surface (existe seulement en tant que *skill* BridgeMemory) | grep `bridgememory` = ∅ | ❌ manquant |
| Dock à onglets | `dockTab` | **Réel** : onglets bridge/skills/editor (slot-swap htmx) | `_bridge.html` (`.dock`, `dock-tabs`), `dock.js` | ✅ (sauf Browser) |
| — onglet Editor (arbo + md) | `fileTree`, `docs` | **Réel** | `_explorer.html`, `workspaces:explorer`, `services/files.py` | ✅ |
| — onglet Skills (cartes groupées draggables) | `skillGroups[]` | **Réel** (panneau) ; drag→pane à revérifier | `skills:panel`, `templates/skills/partials/_panel.html` | ✅/🟡 |
| — onglet Browser (localhost) | `browserUrl` | **Absent** (dock = bridge/skills/editor) | grep onglet browser = ∅ | ❌ manquant |
| — onglet Bridge (voix) | `bridge{}` | **Réel** : orbe standby/listening/thinking/speaking, journal, composer | `_bridge.html` (`data-bridge`), `bridge.js`, `voice/` | ✅ (ASR ≠) |
| Status bar | dérivé | Pied de sidebar `#ws-state` (état WS) ; pas la barre complète | `base.html` | 🟡 partiel |
| Command palette (⌘K) | `palItems` | **Absent** | grep `palette` = ∅ (seul `shortcuts.js` gère des raccourcis) | ❌ manquant |
| Toasts | `toasts[]` | **Réel** | `#toasts` (`base.html`), `shell.js` | ✅ |

## 3. Map des éléments async : simulation maquette → transport réel

Rappel : dans la démo, **zéro** `fetch`/WS — tout est `setTimeout`/`setInterval`.
Voici le transport réel en face.

| « Live » maquette (faux) | Transport réel dans le kit | État |
|---|---|---|
| `runPrompt`→`planFor` (lignes scriptées) | `op:spawn/stdin` → PTY du binaire `claude` → `pane_output` (stdout) streamé par groupe pane | ✅ réel |
| Chat pane (headless) | `op:chat_start/chat_send` → `headless_manager` (stream-json, `--resume`) → `chat_event` | ✅ réel |
| `runSwarm` (séquences `activate/done` + `setInterval`) | mission DAG, **poll htmx `every 4s`** sur `tasker:swarm` (pas de push WS) | 🟡 poll, pas push |
| Board `onColDrop`→`dispatch` | move persisté → `tasker/runner.py` + `signals.py` → dispatch Celery (ADR-3) | ✅ réel |
| Bridge `listen()` (mots un par un + ts) | ASR **push-to-talk upload** (CrisperWhisper serveur) ou WebSpeech ; **pas de partiels streamés word-ts** | 🟡 reporté (S13) |
| `route()`/`parseIntent` (intent → action) | `voice/intents.py` (regex déterministe, ADR-4, `MAX_SPAWN=8`) → `voice/actions.py` → vraies ops | ✅ réel |
| `toast()` | `#toasts` client | ✅ réel |
| densité/cols/`spawnMany` | état de vue vanilla, survit au swap htmx (assets globaux) | ✅ réel |

---

## 4. Les vrais manques (vérifiés, pas supposés)

1. **Command palette ⌘K** — totalement absente. C'est une *addition* de la
   maquette (pas au plan de la roadmap). Surface pure client : liste d'actions
   fuzzy → appelle les endpoints/JS existants. Faible risque, forte valeur UX.
2. **Mode Memory (`.bridgememory` note-graph)** — absent comme surface de
   workspace. À décider : est-ce un vrai besoin produit ou un décor de démo ?
   (BridgeMemory vit déjà comme *skill*, pas comme vue.)
3. **Onglet Browser du dock** — planifié S14 (« Editor, Browser, Skills »), non
   livré. Le dock n'a que bridge/skills/editor. Petit ajout (iframe localhost +
   barre d'URL) dans `_bridge.html`/`dock.js`.
4. **ASR en streaming (word-timestamps) + voix→agent direct** — reporté depuis
   S13, réaffirmé dans `AUDIT.md` S17 « ce qui reste ». C'est le seul écart
   *async* réel de Bridge : passer de l'upload push-to-talk à des partiels
   streamés sur le WS. Nécessite un canal ASR (nouvel `op:` sur `CockpitConsumer`
   ou endpoint dédié) + rendu incrémental côté `bridge.js`.
5. **Swarm en nœuds de rôles agents, poussé en WS** — la maquette montre
   coordinator/builders/scouts/reviewers qui s'allument ; le kit montre les
   **tâches** d'un DAG qui changent d'état, en **poll 4s**. Deux options : (a)
   garder la sémantique tâches (plus honnête, cf §7) et juste la pousser en WS au
   lieu de poller ; (b) ajouter une projection « par agent » par-dessus. Décision
   produit, pas technique.
6. **IA mono-cockpit** (4 modes in-place + view-menu + chrome à feux) — non fait
   **par choix** (multi-pages htmx). Voir §5.

Tout le reste de la « vision » est déjà là, souvent en mieux (agents réels,
budget, reprise, confidentialité observateur, durcissement sécurité).

---

## 5. La décision que je ne prends pas à ta place

La maquette et le kit ont deux **architectures d'information** différentes :

- **Maquette** : un seul écran, 4 modes exclusifs togglés en place (`mode`), dock
  persistant à droite, palette ⌘K, menu de vues en haut.
- **Kit** : des **pages** htmx distinctes (workspace ↔ missions ↔ swarm ↔ régie),
  dock présent sur la vue workspace.

Deux chemins :

**Option A — Converger vers l'IA de la maquette.** Refondre la vue workspace en
cockpit unique à 4 modes + palette + chrome. *Coût élevé*, touche `base.html` et
la navigation, et frotte avec des décisions assumées (`§7`, ADR). Rendu fidèle à
la vision.

**Option B — Greffer les surfaces manquantes sur l'IA actuelle.** Ajouter la
palette ⌘K (qui *navigue* entre les pages existantes), l'onglet Browser, l'ASR
streaming, et pousser le swarm en WS ; laisser Memory en question ouverte.
*Coût faible à moyen*, respecte le codebase et les ADR, livre 80 % de la valeur
perçue de la démo sans refonte.

**Ma recommandation : B**, en assumant que la maquette est une *cible d'UX*, pas
un cahier des charges pixel. Mais c'est ton produit — dis-moi A ou B (ou un
mélange : par ex. palette + Browser + ASR streaming en B, et on rediscute le
mono-cockpit plus tard).

## 6. Sprint proposé (dès que tu as tranché §5)

En **Option B**, ordre par risque croissant, chaque sprint fini par le zip à jour
dans `outputs` + `AUDIT.md`, ton rituel :

- **Sprint P — Command palette ⌘K** : surface cliente, actions = endpoints/JS
  déjà là. Aucun modèle, aucune migration. Vérifiable offline.
- **Sprint Br — Onglet Browser** : 4ᵉ onglet du dock (iframe localhost + URL).
- **Sprint SW — Swarm push** : remplacer le poll htmx 4s par un groupe WS sur
  `CockpitConsumer` (`op:swarm_attach`, event `swarm_state`) ; `_swarm.html`
  écoute au lieu de re-`GET`.
- **Sprint ASR — Voix streaming** : partiels word-ts sur le WS + rendu
  incrémental `bridge.js` + voix→agent direct (les deux reportés de S13).

En **Option A**, on insère d'abord un **Sprint 0 de refonte de shell** (cockpit
unique + modes) avant tout le reste — et là je te fais un audit dédié, parce que
ça touche la navigation de toute l'app.

---

*Rien ici n'a modifié le kit. Ce document est une carte, à valider avant tout
code. Sur ton feu vert (§5), je differe le premier sprint contre le code et je
livre le zip + AUDIT.*
