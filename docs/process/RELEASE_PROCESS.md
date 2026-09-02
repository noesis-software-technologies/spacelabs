# Conduite d'une release — de l'idée au flag nettoyé

## 0. Les quatre principes (non négociables)

1. **Rien n'entre dans `main` sans PR** — pas même un admin (rulesets sans bypass). Un hotfix est une PR.
2. **Pas de merge sans checklist cochée** — la CI lit les lignes `- [x] TOKEN:` de la description de la PR
   et le PO pose `po-approved` après démo. Une case cochée par le dev sans démo est une faute, pas une astuce.
3. **Déployer ≠ releaser** — tout code nouveau vit derrière un feature flag déclaré **avant la première ligne
   de code** (1er commit de `feature/*`). Merger dans `main` ne change rien pour les utilisateurs ;
   la release produit est un **palier de rollout** (`release/<epic>-<palier>` → `main`), validé par le PO,
   mesuré par l'analyste.
4. **Petit, souvent, mesuré** — `main` est toujours déployable, staging est déployé à chaque merge,
   la prod est taguée quand l'EM le décide, et un flag qui traîne > 90 jours ouvre une issue de nettoyage.

## 0'. Les six phases du cycle de vie ↔ les gates du harnais

| Phase (organisation produit) | Qui | Ce que le harnais matérialise |
|---|---|---|
| 1. Discovery & alignement — *pourquoi / quoi* | CPO, Director/GPM, User Researcher, analyste (baseline), PM (PRD), EM + tech lead (faisabilité, doc d'archi) | formulaire **Épic** : problème, hypothèse, North Star, guardrails, non-goals, liens PRD/recherche/baseline/archi, **tier de lancement** ; label `epic:approved` = **Gate 0** |
| 2. Définition & pré-dev — *comment / quand* | Design (maquettes), APM (stories), tech lead (découpage), PMM (plan GTM), ProdOps (calendrier, dépendances) | sous-tâches + **issue de suivi d'intégration** créées par `10-new-epic.sh` = **Gate 1** ; Definition of Ready cochée |
| 3. Développement & QA | devs, data engineer (pipelines), analyste (événements), QA, EM (blocages) | `sub-feature/*` → `feature/*`, checklists, QA Passed, `ci-sub-feature` = **Gate 2** |
| 4. Launch readiness — Go/No-Go | ProdOps (facilite), PM, QA, tech lead, PMM, analyste, CTO (tier 1) | PR d'intégration, `32-go-no-go.sh` (tableau de bord automatique), `po-approved` = **Gates 2' et 3** |
| 5. Déploiement & go-to-market | EM/tech lead (déploiement), QA (smoke prod), PMM (GTM), APM (feedback) | `40-release.sh`, environnement `production`, paliers `35-rollout.sh` = **Gates 4 et 5** |
| 6. Post-launch & itération | analyste (dashboard J+7/J+14), PM (verdict), ProdOps (rétrospective, SOP) | revue post-launch, nettoyage du flag, `flag-hygiene` = **Gate 6** |

## 1. Branches et sens des PR

```
main  ◄──── feature/<epic> ◄──── sub-feature/<epic>/<task>     (une par sous-tâche, une par sub-team)
  ▲
  ├──── release/<epic>-<palier>   (ne touche que config/feature_flags.yml)
  └──── hotfix/<slug>             (correctif urgent, périmètre minimal)
```

- slugs en **kebab-case** (`billing-dashboard`), flags en **snake_case + version** (`billing_dashboard_v1`)
- la base est **déduite du nom** de la branche (`scripts/ci/check_branch.py`) : une PR mal ciblée est rouge
- `sub-feature/*` n'existe que le temps d'une sous-tâche ; `feature/*` le temps d'un épic ; toutes sont
  supprimées au merge (squash)

## 2. Le parcours, gate par gate

### Gate 0 — Cadrage (PM du pod → leadership produit)

1. Le PM ouvre une issue avec le formulaire **« Épic (PM) »** : problème utilisateur, hypothèse,
   **une** North Star metric, **2** guardrails, **3** non-goals, nom du flag, sponsor, Definition of Ready.
2. Le Director PM / GPM lit, challenge, puis pose le label `epic:approved` :
   ```bash
   gh issue edit 42 --add-label epic:approved
   ```
   Sans ce label, rien ne se code (le script de la gate 1 refuse).

### Gate 1 — Préparer le terrain (tech lead)

```bash
scripts/gh/10-new-epic.sh --epic 42 --slug billing-dashboard --pod growth \
    --task "DB migrations" --task "Billing API" --task "UI dashboard"
```
Ce que fait le script, dans l'ordre : vérifie `epic:approved` → crée `feature/billing-dashboard` depuis
`main` → **1er commit = `billing_dashboard_v1: off` dans `config/feature_flags.yml`** → crée une issue
`sub-task` par `--task` rattachée à l'épic (sub-issues + cases dans l'épic) → pose le label `tier:N`
(lu dans le formulaire, ou `--tier`) → crée l'**issue de suivi d'intégration** `[<slug>] Suivi d'intégration`
(label `tracking`, Main Dev Team : les phases à cocher jusqu'au nettoyage du flag ; c'est elle que la PR
d'intégration ferme, l'épic reste ouvert jusqu'à la fin) → imprime la commande de démarrage de chaque sous-tâche.

La hiérarchie des tickets est donc : **Épic** (PM) → **Sous-tâches** (sub-teams, une branche chacune) →
**Suivi d'intégration** (Main Dev Team) — et rien d'autre.

Ensuite, le tech lead pose les **fondations** sur `feature/*` (modèle de données, contrat d'API, squelette
de vue derrière `@flag_required("billing_dashboard_v1")`, commentaires `# sub-team: injecter ici`) et les
pousse par une première `sub-feature/billing-dashboard/scaffold`.

### Gate 2 — Build (sub-teams) et QA

Chaque sub-team, pour sa sous-tâche :
```bash
scripts/gh/20-new-subfeature.sh billing-dashboard billing-api 57      # branche liée à l'issue #57
# … commits …
scripts/gh/25-open-pr.sh 57                                           # PR → feature/billing-dashboard, checklist pré-remplie
```
Ouvrir la PR **tôt, en brouillon** (`25-open-pr.sh 57 --draft`) : la Main Dev Team et le PO voient le travail
en cours et commentent avant la revue formelle ; la checklist incomplète d'un brouillon est tolérée (notice),
elle redevient bloquante au passage en « Ready for review ».
La CI (`ci-sub-feature`) exige : convention de branche · checklist `TICKET AC FLAG TESTS QA` cochée ·
`ruff` · tests unitaires (+ `manage.py check`, migrations à jour) · tests `smoke`.
Le PO peut être demandé en revue d'une sous-tâche pour confronter la réponse de l'API / l'écran aux critères
d'acceptation (`gh pr edit 61 --add-reviewer <login>`). Les conflits de merge dans `feature/*` sont résolus
par le **tech lead** (Main Dev Team), pas par la sub-team.
La QA joue le scénario **sur la branche à jour** puis signe la ligne `QA:` (nom + date). Une revue d'un
code owner est requise (ruleset `harness-feature`). Merge = squash dans `feature/*`.

Mettre à jour sa branche quand `feature/*` avance (le plus simple, sans réécriture d'historique) :
```bash
git fetch origin && git merge origin/feature/billing-dashboard
```

### Gate 2' — Intégration (tech lead → main)

Quand toutes les sous-tâches sont mergées :
```bash
git switch feature/billing-dashboard && git pull
scripts/gh/25-open-pr.sh 42        # PR → main, gabarit integration, `Closes #<suivi>` + `Refs #42`, labels needs-po-review + tier:N
```
La CI (`ci-integration`) exige : checklist `TICKET AC FLAG TESTS QA ROLLBACK ANALYTICS DOCS GTM` ·
**régression complète** · `flag-check` (registre valide, flags du code déclarés, flags périmés signalés) ·
e2e Playwright si `E2E_ENABLED`. Le ruleset `harness-main` exige 2 approbations dont un code owner,
threads résolus, branche à jour.

### Gate 3 — Go / No-Go (ProdOps) puis go du PO

**La réunion Go/No-Go dure 10 minutes parce que le tableau de bord est déjà rempli** :
```bash
scripts/gh/32-go-no-go.sh billing-dashboard            # ou Actions → go-no-go → Run workflow
```
Le script agrège depuis GitHub, par rôle, ce que chacun confirme en réunion, et publie le rapport sur la PR
d'intégration avec le label `go` ou `no-go` :

| Rôle | Ce qu'il confirme | Comment le harnais le lit |
|---|---|---|
| PM | tous les critères d'acceptation sont remplis | sous-tâches fermées, aucune PR `sub-feature/*` ouverte, ligne `AC:` cochée, revues approuvées |
| QA | zéro bug S1/S2 ouvert | issues `bug` ouvertes en S1/S2 citant l'épic (`#42`), le flag ou portant `pod:<slug>` |
| Tech lead | migrations sûres, plan de rollback | ligne `ROLLBACK:` cochée, flag déclaré `off` sur la branche, checks CI verts |
| Analyste | événements de mesure actifs en staging | ligne `ANALYTICS:` cochée |
| PMM | docs support, annonce, enablement ventes prêts (selon tier) | ligne `GTM:` cochée |
| CTO / VP Eng | sign-off d'une release majeure ou risquée | **tier 1** : label `exec-approved` posé par un `EXEC_APPROVERS` |

Un **NO-GO** bloque mécaniquement : tant que le label `no-go` est présent, le check `po-gate` refuse le merge —
on corrige, on relance le script, `go` remplace `no-go`.

Puis le tech lead fait la **démo** des critères d'acceptation au PO (flag ON sur staging ou en local).
Le PO — et lui seul (`PO_APPROVERS`) — pose le label :
```bash
gh pr edit 61 --add-label po-approved
```
Le check `po-gate` passe au vert ; tout nouveau commit **retire** le label (la validation porte sur un état
précis du code). Merge (squash) → `main`.

### Gate 4 — Déploiement (EM)

- chaque merge dans `main` déploie **staging** automatiquement (`release.yml`, flags OFF)
- quand l'EM décide de livrer en prod :
  ```bash
  scripts/gh/40-release.sh minor        # vérifie main vert, tag v1.3.0, push → GitHub Release + job deploy-production
  ```
  le job `deploy-production` attend l'**approbation de l'environnement `production`** (Settings →
  Environments → Required reviewers : EM / tech lead). Toujours flag OFF : la prod ne change pas encore.
- le déploiement réel passe par les **hooks** `deploy/staging.sh` / `deploy/production.sh` (contrat :
  `deploy/README.md`, owner EM) ; juste après, le job `smoke-production` joue `deploy/smoke.sh` (scénarios QA
  contre la prod) ou, à défaut, `GET $PROD_HEALTH_URL` — rouge = repli par redéploiement du tag précédent.

### Gate 5 — Rollout = la release produit (PM + analyste)

```bash
scripts/gh/35-rollout.sh billing-dashboard internal --allow-user alice --allow-user bob   # l'équipe teste en prod
scripts/gh/35-rollout.sh billing-dashboard 10                                             # 10 % des utilisateurs connectés
scripts/gh/35-rollout.sh billing-dashboard 50
scripts/gh/35-rollout.sh billing-dashboard 100                                            # état on → lancement PMM
scripts/gh/35-rollout.sh billing-dashboard off                                            # repli (kill switch)
```
Chaque palier = une PR d'une ligne (`release/<epic>-<palier>` → `main`, gabarit **rollout**) : critères de
passage, métriques surveillées, personne d'astreinte, `po-approved` par le PM. Le déploiement de `main`
propage l'état. Repli d'urgence **sans PR** : `FLAG_BILLING_DASHBOARD_V1=off` dans l'environnement du
service + redémarrage (cf. `docs/process/FEATURE_FLAGS.md`).

Le PMM cale la communication sur le palier 100 % ; l'analyste tient le tableau de bord North Star +
guardrails à chaque palier et dit **stop** si un guardrail casse.

### Gate 6 — Clôture (PM + analyste)

Le passage à 100 % (`35-rollout.sh … 100`) inscrit `released_at` dans le registre ; **J+7** (`POST_LAUNCH_REVIEW_DAYS`),
le workflow `flag-hygiene` ouvre l'issue `[post-launch] Revue J+7 — <flag>` (résultats · verdict · rétrospective),
une seule fois par flag. Entre J+7 et J+14 à 100 % : l'analyste produit le **tableau de bord post-launch** (réel vs North Star et
guardrails de l'épic, comparé à la baseline mesurée en phase 1), le PM anime la **revue post-launch**
(résultat vs hypothèse, surprises, feedback qualitatif remonté par l'APM) et rend le verdict :
- **généraliser** → `scripts/ci/flags_registry.py set --name billing_dashboard_v1 --state permanent`
  puis PR de nettoyage : supprimer les `is_enabled(...)` / `{% if flags.… %}`, retirer l'entrée du registre,
  remplacer les tests des deux chemins par ceux du chemin conservé ;
- **itérer** → nouvel épic (`billing_dashboard_v2`), repousser `cleanup_by` avec la raison ;
- **tuer** → `off`, PR de suppression du code ET du flag.
L'épic est fermé quand le flag n'existe plus. Le workflow `flag-hygiene` rappelle chaque lundi les flags en retard.
ProdOps clôt par une **rétrospective de release** (30 min : ce qui a bloqué, ce qui a été contourné) et
répercute les décisions dans ce document et dans les gates — la procédure évolue par PR sur `docs/process/`
et `.github/`, pas par consigne orale.

## 2'. Tiers de lancement — toutes les releases ne se ressemblent pas

Le tier est choisi dans le formulaire d'épic (ou `--tier` de `10-new-epic.sh`), suit l'épic et ses PR
(`tier:N`) et gouverne le Go/No-Go et les sign-offs :

| Tier | Exemple | Ce qui change dans le harnais | Sign-offs |
|---|---|---|---|
| **1 — Lancement majeur** | nouveau module produit, changement de prix | `GTM:` = plan GTM complet, presse, formation ventes ; paliers de rollout obligatoires ; communication CPO | `epic:approved` · `po-approved` · **`exec-approved`** (CTO/CPO, `EXEC_APPROVERS`) |
| **2 — Release standard** (défaut) | amélioration de workflow très demandée | `GTM:` = notes de release rédigées par le PMM ; géré entièrement dans le pod | `epic:approved` · `po-approved` |
| **3 — Mineur / correctif** | petit ajustement, correctif non urgent | `GTM:` = entrée `CHANGELOG` ; EM + QA suffisent en réunion Go/No-Go | `epic:approved` · `po-approved` (asynchrone) |

Un hotfix n'a pas de tier : profil `hotfix`, gate PO asynchrone, tag `patch`.

## 3. Hotfix (S1 / S2)

```bash
scripts/gh/27-new-hotfix.sh login-500 88     # hotfix/login-500 depuis main, liée au bug #88 (label hotfix posé)
# … test qui échoue avant / passe après, correctif minimal …
scripts/gh/25-open-pr.sh 88                  # PR → main, gabarit hotfix (TICKET TESTS ROLLBACK), label needs-po-review
```
Si le bug est derrière un flag, le repli immédiat est `FLAG_<NOM>=off` ; le hotfix vient après.
Mêmes gates, profil réduit, le PO approuve en asynchrone. Après merge : tag `patch` (`40-release.sh patch`),
puis reporter le correctif dans les `feature/*` ouvertes (`git merge origin/main`).

## 4. Rythme conseillé (release train)

| Quand | Quoi | Qui |
|---|---|---|
| en continu | merges `sub-feature` → `feature`, staging à chaque merge dans `main` | devs, QA |
| chaque semaine (jour fixe) | tag prod `vX.Y.Z` de ce qui est vert et approuvé — sans attendre « la feature » | EM |
| à la demande du PM | paliers de rollout, un à la fois, avec observation | PM, analyste |
| lundi | issues `flag:cleanup` automatiques | flag-hygiene |
| fin d'épic | revue post-launch + nettoyage du flag | PM, analyste, devs |

## 5. Correspondance avec le playbook release (noelabs-pack)

| Gate du playbook | Dans le harnais |
|---|---|
| **Intention** (INTENT.md, ordres permanents) | épic approuvé : North Star / guardrails / non-goals écrits avant le 1er commit |
| **Invariants** (suite pytest, verdict clean/changed/blocked) | job `regression` + `flag-check` + rulesets : pas de merge si rouge |
| **Carte produit** (feature map POV utilisateur) | démo au PO → `po-approved` ; paliers de rollout mesurés ; revue post-launch |
