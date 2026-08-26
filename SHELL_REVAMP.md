# SHELL_REVAMP.md — Sprint 0 : recomposer le cockpit mono-écran (Option A)

**Décision retenue : Option A.** On recompose le cockpit fidèle à la maquette v2
(navbar + header + sidebar + side panels qui slident). La **source de vérité du
design** est `spacelabs-demo.html` lui-même — son `<style>` (l.8-668) et son DOM,
portés sur `--ds-*`. On ne réinvente rien ; on porte.

Rien dans ce document ne modifie encore le kit. C'est l'audit à valider avant code.

---

## 1. Le bug, et pourquoi c'est la racine de l'Option A

Tu l'as vu juste : créer un terminal écrase les partiales. Vérifié :

- `pane_create` (POST) renvoie **le bon fragment** — un seul pane (`entry.partial`)
  + un event `paneCreated`. Ça, c'est correct.
  `apps/workspaces/views.py:145`
- Mais les boutons **Terminal** / **Chat** de la vue ciblent le cockpit entier :
  `hx-target="#content" hx-swap="innerHTML"`.
  `templates/workspaces/partials/_workspace_view.html`

Donc htmx prend ce fragment d'un pane et **remplace tout `#content`** — la toolbar,
`#pane-grid`, et le dock Bridge disparaissent, il ne reste qu'un pane nu.

Ce n'est pas un réglage isolé : c'est le symptôme d'une IA **sans frame
persistant**. Aujourd'hui le « shell » est le *contenu* d'une page (`detail.html`
→ `_workspace_view.html`, rendu dans `#content`). Toute action qui vise `#content`
détruit la composition. L'Option A supprime la cause : un shell rendu une fois,
et des **slots nommés** pour tout le reste.

## 2. La cible : un frame persistant + des slots

Squelette de la maquette (mesuré) :

```
.app  (frame, colonne, max-width 1440, height min(90vh,900))
├── .tbar   (grid 1fr auto 1fr)      ← navbar + header (feux, hexagone, crumb, palette, view-menu, notif, dock-toggle, reset)
├── .body   (flex)
│   ├── .wsp    (246px, slide: .hidden{margin-left:-246px})   ← SIDEBAR gauche (workspaces + mode-switcher)
│   ├── .main   (flex:1, colonne)
│   │   └── .stage (flex:1)          ← RÉGION DE MODE : terminals | board | swarm | memory
│   │       └── .tgrid-wrap > .tgrid ← grille de panes (#pane-grid)
│   └── .dock   (340px, slide: .hidden{margin-right:-340px})  ← SIDE PANEL droit (onglets bridge/skills/editor/browser)
├── .sbar   (24px)                    ← barre de statut
├── .pal    (overlay)                 ← command palette ⌘K
└── .toasts
```

| Région | Rôle | Persiste ? | Cible de swap ? |
|---|---|---|---|
| `.tbar` (navbar + header) | chrome global + contexte | ✅ rendu 1× | non |
| `.wsp` (sidebar) | workspaces + modes | ✅ | son contenu via `workspaces:sidebar` |
| `.main > .stage` | contenu du mode courant | frame ✅ | **oui — `#stage`** (switch de mode) |
| `.tgrid` / `#pane-grid` | grille de panes | ✅ (dans stage terminals) | **oui — append `beforeend`** |
| `.dock` | side panel droit | ✅ | ses `[data-dock-slot]` (déjà en place) |
| `.sbar` | statut | ✅ | non (JS met à jour le texte) |
| `.pal`, `.toasts` | overlays | ✅ | non |

Le slide gauche/droite est **CSS pur** (`.hidden` + transition), togglé par les
boutons panelLeft/panelRight — client, aucun aller-retour serveur.

## 3. Le contrat de slots (le cœur anti-régression)

**Règle d'or : aucune action in-cockpit ne cible `#content`.** Chaque action vise
son slot et rend son fragment. On garde `render_htmx` (« une URL, deux
représentations ») tel quel.

| Action | `hx-target` | `hx-swap` | Fragment rendu | Existe ? |
|---|---|---|---|---|
| Créer un pane (pty/headless) | `#pane-grid` | `beforeend` | `entry.partial` (déjà bon) | 🔧 changer la cible |
| Supprimer un pane | `#pane-<id>` | `delete`/OOB | `""` (déjà) | 🔧 |
| Vider l'empty-state à la 1ʳᵉ création | — | via event `paneCreated` (déjà émis) | JS listener | 🔧 |
| Switch de mode terminals/board/swarm/memory | `#stage` | `innerHTML` | fragment de stage (par mode) | 🆕 vues stage |
| Onglet dock (bridge/skills/editor) | `[data-dock-slot=…]` | `innerHTML`/`afterbegin` | déjà branché | ✅ |
| Onglet dock **browser** | `[data-dock-slot='browser']` | `innerHTML` | iframe + URL | 🆕 |
| Sidebar (liste workspaces) | dans `.wsp` | `innerHTML` | `_sidebar_list.html` | ✅ |
| Command palette ⌘K | overlay | — | actions = liens htmx vers les slots ci-dessus | 🆕 |

## 4. Inventaire des partiels : maquette → Django (on réutilise l'existant)

| Bloc maquette | Devient | Réutilise le kit ? |
|---|---|---|
| `.tbar` | `_topbar.html` (navbar+header) | 🆕 (remplace le chrome `base.html` actuel dans le cockpit) |
| `.wsp` | `_sidebar.html` + `_sidebar_list.html` | partiel existant `_sidebar_list.html` ✅ |
| `.stage` terminals + `.tgrid` | `_stage_terminals.html` + `_pane_pty.html`/`_pane_headless.html` | panes existants ✅ |
| `.stage` board | `_stage_board.html` | `tasker/partials/_board.html` ✅ |
| `.stage` swarm | `_stage_swarm.html` | `tasker/partials/_swarm.html` ✅ |
| `.stage` memory | `_stage_memory.html` | ❌ à créer (surface absente) |
| `.dock` | `_dock.html` (frame + onglets) | `_bridge.html` (dock actuel) ✅ + `_explorer.html`, `skills:panel` |
| `.sbar` | `_statusbar.html` | 🆕 |
| `.pal` | `_palette.html` | 🆕 |
| `.toasts` | déjà dans `base.html` | ✅ |

## 5. Design v2 — non négociable

Le look (near-black, orange, hexagone, densités, géométrie) vient de la maquette,
pas d'une réinvention. Deux règles :

1. Le `<style>` de la démo est la **référence visuelle**. On le porte en réutilisant
   les tokens `--ds-*` du kit (BRAND.md fait autorité) et en **réconciliant** les
   alias courts de la démo (`--orange`, `--blue`, `--claude`, `--cyan`, `--gold`,
   `--pink`, `--green`, `--red`, `--purple`) vers `--ds-*` — une couche d'alias, pas
   une divergence.
2. Les **94 classes CSS déjà livrées sans template** (`dock*`, `bridge*`, `pane-splash*`,
   `pane-prompt*`, `term-line--*`… — cf `ROADMAP.md §1`) sont la carte des surfaces :
   le shell les consomme. On aligne les noms de classes de la démo sur celles-là quand
   elles existent déjà, plutôt que d'en inventer des parallèles.

## 6. Séquence du Sprint 0 (chaque étape vérifiable offline)

Objectif : le cockpit se **compose** et ne s'**écrase** plus. Zéro changement de
backend — présentation + ciblage seulement.

1. **Frame persistant** : `_workspace_view.html` devient le shell complet
   (`.tbar` + `.body(.wsp|.main|.dock)` + `.sbar` + `.pal`) rendu par `detail`.
   Les panes s'affichent dans `#pane-grid` à l'intérieur de `.stage`.
2. **Correctif de ciblage** : boutons Terminal/Chat → `hx-target="#pane-grid"
   hx-swap="beforeend"` ; listener `paneCreated` retire `#pane-grid-empty` et
   incrémente le badge « en cours ». Le bug de la §1 disparaît ici.
3. **Slot `#stage` + switch de mode** : 4 vues stage (terminals réutilise
   l'existant, board/swarm branchent les partiels tasker, memory = placeholder)
   swappées dans `#stage` sans toucher au chrome.
4. **Dock unifié** : `_dock.html` absorbe le dock actuel + prévoit le 4ᵉ onglet
   (browser, coquille vide pour l'instant).
5. **Port du design v2** : CSS de la démo → `--ds-*` + alias, appliqué au shell.
6. **Vérif** : `manage.py check` 0 issue ; suite verte (les tests existants ne
   doivent pas casser) ; **live** — créer un terminal **n'écrase plus** toolbar/dock,
   switch de mode conserve le chrome, panels slident. Puis zip + `AUDIT.md`.

Les sprints features (palette ⌘K, onglet Browser, ASR streaming, swarm poussé en
WS, mode Memory) se **branchent ensuite sur les slots** définis ici — d'où l'ordre :
le shell d'abord, les surfaces après.

## 7. Ce que je ne touche pas

Le backend réel ne bouge pas : `CockpitConsumer`, PTY/`pane_manager`, `tasker`
(planner/runner/graph), `voice` (intents déterministes, ADR-4), observer, ops. On
recompose la **présentation** et on corrige le **ciblage htmx**. Les ADR tiennent,
les 495 tests restent la barre.

---

*Sur ton feu vert, je démarre le Sprint 0 : shell composé + contrat de slots +
correctif `pane_create`, vérifié offline, livré en zip + AUDIT.*
