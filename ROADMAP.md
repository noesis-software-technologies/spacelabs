# ROADMAP — SpaceLabs S9 → S16

> **Cible en une phrase.** Un workspace = *n* instances Claude Code qui
> travaillent en parallèle sous la conduite d'un **Master Tasker** qui découpe,
> distribue, surveille et recolle le travail — le tout pilotable à la voix et
> diffusable en direct.

Ce document part du code réel (128 tests verts, S1→S8 livrés), pas d'une page
blanche. Chaque sprint indique ce qu'on ajoute, ce qu'on ne casse pas, et
comment on prouve que c'est fini.

---

## 1. Où on en est vraiment

Mesuré sur le zip, pas déclaré :

| Brique | État | Preuve |
|---|---|---|
| PTY multi-panes + WS multiplexé | ✅ solide | `pane_manager.py`, ops `spawn/attach/stdin/kill` |
| Chat headless `stream-json` + reprise `--resume` | ✅ solide | `headless_manager.py`, `HeadlessPane.claude_session_id` |
| Registre polymorphe de panes | ✅ **c'est le levier** | `models.registry`, `concrete_panes` |
| Observateur SSE + confidentialité | ✅ solide | `apps/observer`, invariants privacy |
| Ops (Celery, jauges, zombies, MCP) | ✅ solide | `apps/ops/services.py` (fonctions pures DB) |
| Voix (CrisperWhisper serveur) | ⚠️ push-to-talk *upload*, pas streaming | `apps/voice/backends.py` |
| Design system | ✅ adopté, densité active | `--ds-*`, `[data-density]` |
| **n instances par workspace** | ✅ **S9 livré** | `capacity.py`, `Workspace.max_panes`, 18 tests |
| **Master Tasker** | ✅ **S10 livré** (mécanique, sans IA) | `apps/tasker`, 23 tests · **prochain : S11 planner** |
| Board / Swarm / Dock | ❌ CSS présent, surfaces absentes | 94 classes définies non utilisées |

### Ce que le design system attend déjà et qui n'existe pas

Le CSS livré contient **94 classes sans template** : `dock*`, `bridge*`,
`skill*`, `explorer*`, `tree-*`, `md*`, `pane-splash*`, `pane-prompt*`,
`term-line--*`, `observer-voice*`. Ce n'est pas du gras : c'est la carte des
surfaces à construire. La roadmap ci-dessous les consomme dans l'ordre.

---

## 2. Les trois verrous à lever

### 2.1 Verrou n°1 — le plafond de panes est faux ✅ *corrigé en S9*

Trois bugs qui se combinent :

1. **`COCKPIT_MAX_PANES` est global au processus, pas par workspace ni par
   owner** : `pane_manager.spawn()` teste `len(self.panes) >= MAX_PANES` sur le
   dict de *tous* les panes, tous propriétaires confondus. À 12, deux
   utilisateurs à 6 panes bloquent tout le monde.
2. **Le chat headless n'est pas plafonné du tout** : `HeadlessManager.start()`
   n'a aucun contrôle de cap. On peut ouvrir 100 sessions `claude -p`.
3. **La jauge ment** : `usage_for_owner()` affiche `active / MAX_PANES` en
   mélangeant les deux familles alors que le cap ne s'applique qu'à une.

Conséquence : « n instances par workspace » n'est pas réglable aujourd'hui.
C'est le premier chantier.

### 2.2 Verrou n°2 — rien ne sait parler à un pane de façon générique ✅ *corrigé en S9*

Le Tasker doit envoyer une consigne à *n'importe quel* pane sans savoir son
type. Or « envoyer » n'a pas la même forme selon le type :

- `PtyPane` → écrire dans stdin (`pane_manager.write`, bytes, base64)
- `HeadlessPane` → `chat_send` (JSON, session Claude)

Le registre polymorphe existe déjà et c'est exactement le bon endroit :
il lui manquait une **capacité `dispatch`** — ajoutée en S9
(`apps/runtime/dispatch.py`, résolution paresseuse, `can_autocomplete`). Sans ça, le Tasker finira en
`if pane.kind == …`, ce que l'architecture interdit (§6.9 du blueprint).

### 2.3 Verrou n°3 — on ne sait pas dire « c'est fini »

Pour orchestrer, il faut un signal de fin fiable par tâche.

- **Headless : disponible.** L'événement `result` de `stream-json` porte
  `cost_usd`, `duration`, `is_error`. C'est un signal propre, déjà persisté
  dans `EventLog`.
- **PTY : indisponible.** Le flux est de l'ANSI opaque, et l'invariant n°1
  interdit de le parser pour en tirer du sens métier. **On ne le contournera
  pas.**

⇒ **Décision d'architecture (ADR-1) : les tâches pilotées par le Tasker
s'exécutent sur des panes headless.** Le PTY reste le mode « je conduis
moi-même ». Un pane PTY peut *recevoir* une consigne dictée, mais il n'entre
pas dans la boucle de complétion automatique. C'est une limite assumée, pas un
oubli — la contourner demanderait de violer l'invariant n°1.

---

## 3. Le Master Tasker — architecture cible

```
                    ┌─────────────────────────────────────────┐
   voix / texte ───▶│  Mission (objectif, budget, workspace)   │
                    └───────────────┬─────────────────────────┘
                                    │  planification
                    ┌───────────────▼─────────────────────────┐
                    │  Planner = 1 pane headless dédié         │
                    │  claude -p → JSON strict → Task[]        │
                    └───────────────┬─────────────────────────┘
                                    │  DAG de tâches
                    ┌───────────────▼─────────────────────────┐
                    │  Dispatcher (service pur DB + Celery)    │
                    │  assigne Task → pane libre (capacité)    │
                    └───────┬──────────┬──────────┬───────────┘
                            ▼          ▼          ▼
                        pane #1    pane #2    pane #n   (Claude Code)
                            │          │          │
                            └──────────┴──────────┘
                                 events `result`
                                       │
                            statut, coût, reprise, replan
```

**Trois principes non négociables**, tirés de ce qui marche déjà dans le projet :

1. **Le Dispatcher est un service pur DB** (comme `apps/ops/services.py`). Le
   worker Celery ne voit pas les managers en mémoire : tout passe par la base.
   L'assignation se fait sous `select_for_update(skip_locked=True)` — deux
   workers ne peuvent pas donner la même tâche à deux panes.
2. **Le planificateur est un pane comme un autre.** Pas de client Claude
   parallèle : on réutilise `HeadlessManager`, `EventLog`, la reprise
   `--resume`, les jauges de coût. Un bug corrigé dans le pipeline profite aux
   deux.
3. **Le Tasker propose, l'humain dispose.** Mode `manual` par défaut : le plan
   s'affiche, on valide avant dispatch. Le mode `auto` est une option par
   mission, avec plafond de coût et d'itérations.

### Modèles (S10)

```python
class Mission(models.Model):
    workspace   = FK(Workspace)            # tenancy via workspace__owner
    goal        = TextField()              # l'objectif en clair
    status      = draft|planning|running|paused|done|failed
    mode        = manual|auto              # auto = dispatch sans validation
    planner_pane = FK(HeadlessPane, null)  # le pane qui planifie
    budget_usd  = Decimal(null)            # plafond dur, coupe le dispatch
    max_parallel = PositiveSmallInt(3)     # n instances simultanées
    created_at / updated_at

class Task(models.Model):
    mission   = FK(Mission, related_name="tasks")
    key       = SlugField()                # "T1" — référencé par depends_on
    title     = CharField(200)
    brief     = TextField()                # la consigne envoyée à l'agent
    status    = todo|ready|assigned|running|review|done|failed|blocked
    depends_on = M2M("self", symmetrical=False)   # DAG
    attempts  = PositiveSmallInt(0)
    max_attempts = PositiveSmallInt(2)
    cost_usd  = Decimal(0)
    order     = PositiveInt

class Assignment(models.Model):
    task      = FK(Task)
    pane      = FK(Pane)                   # base, pas HeadlessPane : polymorphe
    started_at / ended_at / outcome
```

### Capacité `dispatch` sur le registre (S9)

```python
register(
    "headless", HeadlessPane, "Chat",
    partial=…, form_path=…,
    dispatch="apps.runtime.dispatch:headless_dispatch",   # ← nouveau
    can_autocomplete=True,                                # ← signal de fin fiable
)
```

Le Dispatcher fait `registry[pane.kind].dispatch(pane, brief)` — jamais
d'`isinstance`, jamais de `if kind ==`. Ajouter un type d'agent (Codex, Cursor)
= 1 modèle + 1 form + 1 partial + 1 ligne de registre, comme aujourd'hui.

---

## 4. Les sprints

### S9 — Fondations « n instances » ✅ **LIVRÉ**

**Objectif.** Rendre le nombre d'agents par workspace réglable, honnête et lisible.

- `COCKPIT_MAX_PANES` → **cap par workspace** (`Workspace.max_panes`, défaut
  settings) + cap global par owner. `pane_manager.spawn()` compte par owner ;
  `HeadlessManager.start()` **applique le même cap** (bug §2.1).
- `usage_for_owner()` compte les deux familles ; jauge `data-level` ok/warn/full.
- **Registre : capacité `dispatch` + `can_autocomplete`** (§3) et
  `apps/runtime/dispatch.py` avec les deux adaptateurs (pty/headless).
- UI : ✅ **fait dans cette passe** — segmented control densité (4 paliers) +
  colonnes (auto/2→6), compteur `n/max`, `.pane-action` (les actions s'effacent
  en dense/micro), badges d'agents en sidebar.
- **DoD.** ✅ 16 agents dans un workspace, plafonds par workspace ET par compte,
  aucun blocage croisé entre deux comptes, headless plafonné, jauge honnête.
  **18 tests S9** (`test_capacity_s9.py`, `test_consumer_capacity_s9.py`),
  suite totale **146 verts**. Vérifié aussi sur serveur local réel (daphne).

### S10 — `apps/tasker` : modèles, board, dispatch déterministe ✅ **LIVRÉ**

**Objectif.** Toute la mécanique d'orchestration, pilotée à la main. Si ça
marche sans IA, l'IA ne fera qu'écrire les tâches.

- Modèles Mission/Task/Assignment + admin + tenancy `for_owner`.
- `services.py` **pur DB** : `ready_tasks(mission)` (résolution du DAG),
  `claim_next(pane)` sous `select_for_update(skip_locked=True)`,
  `complete(task, outcome, cost)`, `fail(task)` + retry.
- Tâche Celery `tasker.tick` (2 s) : pour chaque mission `running`, assigner les
  tâches prêtes aux panes libres jusqu'à `max_parallel`.
- **Surface Board** (kanban) : colonnes todo/ready/running/review/done,
  glisser-déposer → changement de statut, carte = titre + agent + coût.
  Consomme le CSS board du design system.
- **DoD.** ✅ DAG respecté (dépendance échouée ⇒ BLOCKED, pas de lancement),
  `select_for_update(skip_locked=True)` prouvé (2 agents / 1 tâche ⇒ 1 seule
  assignation), retries bornés, budget qui met en pause, filtre ADR-1 (le PTY
  n'est jamais éligible). **23 tests S10**, suite totale **194 verts**, board
  vérifié sur serveur local (mission créée, tâche ajoutée, DAG résolu).

### S12 — Le Planner : Claude écrit le plan ✅ **LIVRÉ**

**Objectif.** Transformer un objectif en clair en DAG de tâches.

- `planner.py` : prompt système strict → **JSON only** (`{"tasks":[{key,title,
  brief,depends_on}]}`), parsé et validé par un `PlanForm`/pydantic-like ;
  refus explicite si le JSON est invalide (pas de « best effort » silencieux).
- Le planificateur est un `HeadlessPane` dédié (`Mission.planner_pane`),
  invisible dans la grille (flag `is_system`), donc gratuit en réutilisation :
  reprise, coût, EventLog, tout est déjà là.
- **Replan** : `replan(mission, feedback)` relance le planner avec l'état
  courant (tâches faites/échouées) — c'est là que `--resume` paie.
- Garde-fous : `budget_usd` coupe le dispatch ; `max_attempts` par tâche ;
  mode `manual` = le plan attend validation humaine.
- **DoD.** « Ajoute des tests au module auth » → plan de 4–6 tâches cohérentes,
  validation humaine, exécution, une tâche échoue → replan propose un correctif.

### S11bis — Boucle de vie complète ✅ **LIVRÉ** *(remonté avant le planner)*

- Détection de fin par événement `result` (headless) branchée sur
  `complete()` — via signal sur `EventLog`, pas de polling.
- Reprise après redémarrage : missions `running` réconciliées au boot
  (`reconcile_boot` existe déjà pour les panes — même mécanisme, `runtime_boot_id`).
- Tâches bloquées : timeout par tâche, détection de pane mort → réassignation.
- Coût réel par mission agrégé depuis `EventLog` (déjà calculé par `apps/ops`).
- **DoD.** `kill -9` sur Daphne au milieu d'une mission → au redémarrage, les
  tâches en vol repartent ou sont marquées, zéro tâche fantôme.

### S13 — Bridge : la voix devient un canal d'orchestration ✅ **LIVRÉ** *(ASR streaming reporté)*

**Objectif.** Passer du push-to-talk *upload* au flux, et brancher la voix sur
le Tasker.

- **Streaming ASR** : `apps/voice` passe d'un POST `multipart` à un
  **WebSocket** `/ws/voice/` (frames audio → partiels). CrisperWhisper est
  verbatim et donne des **timestamps par mot** : c'est ce qui permet d'afficher
  le partiel honnêtement, mot à mot.
- **Routeur d'intentions** (`apps/voice/intents.py`), déterministe et testable :
  `statut` / `spawn n` / `dispatch pane N` / `mission …` / `densité …`.
  Le LLM n'intervient **pas** ici — une regex qui rate est réparable, une
  hallucination qui tue un pane ne l'est pas.
- **Surface Bridge** : le dock droit + l'orbe, le journal de transmission, les
  tâches. Tout le CSS existe (`bridge*`, `dock*`).
- **DoD.** « lance une mission : migrer les tests auth » crée la mission, la
  planifie, et la lance — sans toucher au clavier.

### S14 — Dock : Editor, Browser, Skills

- Onglets du dock (CSS `dock-tab*` prêt) : arborescence de fichiers
  (`explorer*`, `tree-*`), rendu markdown (`md*`) pour lire `CLAUDE.md`/AGENTS.md
  depuis le cockpit, aperçu navigateur.
- **Skills** = fragments de prompt versionnés en base, **glissables sur un pane**
  (CSS `skill*` prêt). C'est le mécanisme le plus rentable du lot : capitaliser
  les consignes qui marchent.
- **DoD.** Glisser « Revue sécurité » sur un pane envoie le prompt correspondant.

### S15 — Swarm & vue télé augmentée

- Vue **Swarm** : le DAG de la mission en graphe (coordinateur au centre,
  tâches en éventail), lecture seule, statut en direct par les mêmes événements.
- Observateur : bandeau vocal (`observer-voice*`, CSS prêt), compteur d'agents
  (✅ fait), pagination au-delà de 9 panes (`observer-overflow-note`) — un mur
  de 16 agents n'est pas lisible à 3 m.
- **DoD.** Une mission suivie de bout en bout depuis la vue télé, sans contrôle.

### S16 — Durcissement

- Perf 16 panes : profilage du fan-out channel layer, coalescing des trames,
  budget mémoire des ring buffers (`COCKPIT_BUFFER_BYTES` × n).
- Sécurité : revue de la liste blanche des commandes, cloisonnement des cwd de
  mission, `check --deploy` vert.
- Docs : CLAUDE.md à jour, ADR consignés, guide « ajouter un type d'agent ».

---

## 5. Ordre, dépendances, et ce qu'on peut paralléliser

```
S9 (socle) ──▶ S10 (tasker mécanique) ──▶ S11 (planner IA) ──▶ S12 (fiabilité)
   │                     │
   │                     └──▶ S15 (swarm, lecture seule)
   └──▶ S13 (bridge/voix) ──▶ S14 (dock/skills)
```

- **S9 bloque tout le reste** : ne pas démarrer S10 avant que le cap et la
  capacité `dispatch` soient en place.
- S13/S14 (voix, dock) sont parallélisables par une autre personne dès S10.
- S15 ne demande aucune écriture : uniquement de la lecture d'état.

## 6. Décisions d'architecture

| # | Décision | Pourquoi |
|---|---|---|
| ADR-1 | Les tâches auto-pilotées tournent sur des panes **headless** | Le PTY n'a pas de signal de fin exploitable sans violer l'invariant n°1 (ne pas parser le flux) |
| ADR-2 | Le Planner est un **pane headless** comme les autres | Réutilise reprise, coût, EventLog, observateur — zéro pipeline parallèle |
| ADR-3 | Le Dispatcher est un **service pur DB** + Celery | Le worker ne voit pas les managers en mémoire (leçon S5) |
| ADR-4 | Le routage d'intentions vocales est **déterministe** | Une regex qui rate se corrige ; une hallucination qui tue un pane, non |
| ADR-5 | `dispatch` est une **capacité du registre** | Interdit les `if kind ==` dans l'orchestrateur (§6.9) |
| ADR-6 | Mode **manual par défaut**, budget obligatoire en auto | n agents en parallèle = n fois la facture et n fois les dégâts |

## 7. Ce qu'on ne fait pas (et pourquoi)

- **Pas de parsing du flux PTY** pour deviner la fin d'une tâche → invariant n°1.
- **Pas de multi-machines** (agents distribués sur plusieurs hôtes) : le produit
  est local-first, Django tourne sur l'hôte pour accéder à `~/.claude`. Ce serait
  un autre produit.
- **Pas de reproduction de la maquette à l'identique** : Board/Swarm/Bridge sont
  repris, mais la maquette simule ses agents ; ici ils sont réels, donc les états
  intermédiaires (assignation, retry, budget) existent et doivent être montrés.
- **Pas d'IA dans le chemin critique du dispatch** (ADR-4).
