# L'équipe dans le harnais — qui signe quoi

L'organigramme d'une organisation produit SaaS mature (exécutif → leadership produit → pods → support
central) est projeté sur des **équipes GitHub** (`scripts/gh/00-bootstrap-teams.sh`), des **règles de
propriété** (`.github/CODEOWNERS`) et des **gates** (workflows + rulesets). Un rôle n'existe dans le
harnais que par ce qu'il signe.

## 1. Organigramme → équipes GitHub

| Couche | Rôle (organigramme) | Équipe GitHub `@org/…` | Ce qu'il/elle signe dans le harnais |
|---|---|---|---|
| Exécutif — le *pourquoi* et le *où* | CPO / VP Product, CTO / VP Engineering | `cpo-office` | Objectif stratégique et budget d'une initiative. **Tier 1** : sign-off `exec-approved` sur la PR d'intégration (`EXEC_APPROVERS`). Lisent les épics et les rapports Go/No-Go. Peuvent siéger dans `product-leadership` pour approuver un épic. |
| Leadership produit — le *quoi* et le *quand* | Director of PM, Principal PM, Group PM | `product-leadership` | **Gate 0** : label `epic:approved` sur l'épic. Sans lui, `10-new-epic.sh` refuse de créer `feature/*`. Owners de `docs/process/`. |
| Pod — PM | Senior PM / PM / APM | `product-managers` (+ `pod-<slug>`) | Rédige l'épic (formulaire « Épic (PM) » : North Star, guardrails, non-goals). **Gate 3** : pose `po-approved` sur les PR → `main` (approbateurs listés dans `PO_APPROVERS`). Co-owner de `config/feature_flags.yml`. Décide chaque palier de rollout. |
| Pod — Design | Product Design Lead, Senior UX, User Researcher | `design` | Owner de `docs/design/`. Wireframes = condition de la Definition of Ready de l'épic ; le User Researcher valide l'hypothèse du PM (entretiens, tests d'utilisabilité) avant `epic:approved`. |
| Pod — Eng | Engineering Manager | `eng-managers` | Owner de `deploy/` (hooks `staging.sh` / `production.sh` / `smoke.sh`) et `release.yml` ; **reviewer requis de l'environnement `production`** (déploiement). Coupe les releases (`40-release.sh`), supervise les hotfix (`27-new-hotfix.sh`). |
| Pod — Eng | Technical Lead / Architecte | `tech-leads` | **Gate 1** : prépare le terrain (`10-new-epic.sh`), 1er commit = flag OFF. Code owner de repli sur `*`, des migrations, des settings. Ouvre la PR d'intégration. |
| Pod — Eng | Frontend developers | `frontend` | Owner de `templates/`, `static/`, `frontend/`. Travaillent sur `sub-feature/*`. |
| Pod — Eng | Backend developers | `backend` | Owner de `apps/` et des migrations (avec les tech leads). Travaillent sur `sub-feature/*`. |
| Pod — Eng | QA / Automation engineer | `qa` | **Gate 2** : signe la ligne `QA: QA Passed — @qa le <date>` de chaque PR (vérifiée par la CI). Owner de `tests/e2e`, `tests/smoke`, `tests/regression`. |
| Pod — Growth | Product Data Analyst | `data-analysts` | Mesure la **baseline** avant le cadrage (DoR). Valide la ligne `ANALYTICS:` de la PR d'intégration (événements North Star + guardrails actifs en staging). Tient le tableau de bord des paliers et produit le dashboard post-launch (J+7/J+14). |
| Pod — Growth | Product Marketing Manager | `pmm` | Owner de `docs/launch/`. Rédige le plan GTM en phase 2 ; signe la ligne `GTM:` de la PR d'intégration (selon le tier : GTM complet / notes de release / changelog). Notifié par `release.yml` ; cale la communication sur le palier 100 %. |
| Central | Head of Product Operations | `prodops` | **Owner du harnais** (`.github/`, `scripts/`, `harness.config.sh`). Seul à changer une gate. Admin du dépôt. Tient le calendrier de release et les dépendances entre pods ; **facilite le Go/No-Go** (`32-go-no-go.sh`) et la rétrospective de release ; définit les tiers de lancement. |
| Central | Data Engineer / Data Scientist | `data-platform` | Owner de `pipelines/`, co-owner de `analytics/`. |

Les équipes `pod-<slug>` (une par pod de `harness.config.sh`) servent aux **labels et aux assignations**
(`pod:growth`…), pas à la propriété de code : le code est possédé par discipline, le travail par pod.

## 2. RACI d'une release (R = fait, A = signe, C = consulté, I = informé)

| Gate | Artefact / action | PM pod | Leadership produit | Tech lead | Devs | QA | Analyste | PMM | EM | ProdOps |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 Cadrage | Issue épic (problème, North Star, guardrails, non-goals, flag, **tier**, PRD, recherche, baseline) | R | **A** (`epic:approved`) | C (doc d'archi) | – | – | R (baseline) | C (plan GTM) | C | C (calendrier) |
| 1 Terrain | `feature/<epic>` + flag OFF (1er commit) + sous-tâches + issue de suivi | C | I | **R/A** | I | – | – | – | I | – |
| 2 Build | PR `sub-feature/*` → `feature/*` : checklist, revue code owner, QA Passed | C | – | A (revue) | R | **A** (`QA:`) | – | – | – | – |
| 2' Intégration | PR `feature/*` → `main` : régression, flag-check, 2 revues, rollback, analytics | C | – | **R** | – | A (`QA:`) | A (`ANALYTICS:`) | C (`DOCS:`) | I | – |
| 3 Go / No-Go | Rapport `32-go-no-go.sh` (labels `go`/`no-go`), tier 1 : `exec-approved` (CTO/CPO) | A (AC) | I | A (rollback) | – | A (0 bug S1/S2) | A (événements) | A (GTM) | C | **R** (facilite) |
| 3' Go PO | Label `po-approved` après démo | **A** | I | R (démo) | – | C | C | I | – | – |
| 4 Déploiement | Merge (squash) → staging auto ; tag `vX.Y.Z` → prod (environnement approuvé) | I | – | R | – | – | – | I | **A** (env. `production`) | – |
| 5 Rollout | PR `release/<epic>-<palier>` → `main` (interne → 10 → 50 → 100) | **A** (`po-approved`) | I | R | – | C | **R** (mesure) | R (lancement à 100 %) | I | – |
| 6 Clôture | Dashboard post-launch (J+7/14), verdict (généraliser / itérer / tuer), PR de nettoyage du flag, rétrospective de release | **A** | I | R | R | – | R (dashboard) | I | – | R (rétro, SOP) |
| ∞ Harnais | Toute modification de `.github/`, `scripts/`, gates | – | C | C | – | – | – | – | – | **A** |

## 3. Qui pose quel label

| Label | Posé par | Effet |
|---|---|---|
| `epic:approved` | `product-leadership` | autorise `10-new-epic.sh` à créer `feature/<epic>` |
| `tier:1` / `tier:2` / `tier:3` | `10-new-epic.sh` (depuis le formulaire d'épic) | tier de lancement ; recopié sur les PR d'intégration et de palier ; tier 1 ⇒ `exec-approved` requis |
| `tracking` | `10-new-epic.sh` | issue de suivi d'intégration de la Main Dev Team, fermée par la PR d'intégration |
| `go` / `no-go` | automatique (`32-go-no-go.sh`) | verdict du tableau de bord Go/No-Go ; `no-go` bloque `po-gate` |
| `exec-approved` | un login de `EXEC_APPROVERS` (CTO/CPO) | sign-off exécutif d'un lancement tier 1 (retiré si posé par quelqu'un d'autre) |
| `severity:S1..S4` | QA (optionnel : le formulaire de bug porte déjà la sévérité) | S1/S2 lié à l'épic ⇒ NO-GO |
| `po-approved` | un login de `PO_APPROVERS` (PM/PO) | check `po-gate` vert → merge dans `main` possible ; retiré automatiquement à chaque nouveau commit (`PO_GATE_STRICT`) ; retiré si posé par quelqu'un d'autre |
| `needs-po-review` | automatique (`po-gate`) | signale au PM qu'une PR → `main` attend |
| `qa-passed` | `qa` (optionnel, visuel) | la preuve qui compte est la ligne `QA:` signée dans la PR |
| `flag:cleanup` | automatique (`flag-hygiene`, lundi) | issue de nettoyage d'un flag périmé |
| `post-launch` | automatique (`flag-hygiene`, J+`POST_LAUNCH_REVIEW_DAYS` après le palier 100) | revue post-launch + rétrospective de release, une par flag lancé |
| `harness` | ProdOps | modification du harnais lui-même |

## 4. Sans organisation GitHub (dépôt personnel)

Il n'y a pas d'équipes : remplace dans `CODEOWNERS` chaque `@org/équipe` par un ou plusieurs `@login`,
et renseigne `PO_APPROVERS` avec les logins des PM. Tout le reste (workflows, rulesets, scripts) fonctionne
à l'identique — les rulesets nécessitent GitHub Team/Enterprise sur un dépôt privé.
