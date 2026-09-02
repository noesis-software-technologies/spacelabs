# HARNESS.md — le harnais de release appliqué à SpaceLabs

Posé par la PR `chore/release-harness` (2026-09-02). Trois équipes de dev (dont des agents IA) travaillent
sur ce dépôt : le harnais est ce qui garantit qu'elles construisent **le même produit** sans se marcher
dessus ni casser `main`. Vue d'ensemble : `RELEASE_PROCESS.md` · rôles : `TEAM.md` · coexistence des
équipes : `AI_TEAMS.md` · flags : `FEATURE_FLAGS.md` · git pas-à-pas : `GIT_CHEATSHEET.md`.

## Token (fine-grained) — permissions nécessaires pour que Claude termine seul

Sur ce dépôt uniquement : **Contents** RW (déjà là) · **Workflows** RW (pousser `.github/workflows/`) ·
**Pull requests** RW (ouvrir les PR) · **Issues** RW (labels, épics, sous-tâches, Go/No-Go) ·
**Variables** RW (variables du dépôt) · plus tard **Administration** RW le temps de poser les rulesets
(`30-protect-branches.sh`), puis à retirer. Révoquer le token après l'installation : il a circulé en clair.

## Ce qui est déjà en place (posé avec la PR, sans rien casser)

- Workflows `ci-sub-feature` / `ci-integration` / `po-gate` / `go-no-go` / `flag-hygiene` / `release`
  (parqués dans `harness/workflows/` tant que le token n'a pas la permission Workflows — voir son README) —
  **consultatifs** tant que les rulesets ne sont pas posés : une PR rouge reste mergeable, le commentaire
  automatique explique quoi corriger. `ci.yml` historique = filet post-merge sur `main` uniquement.
- Labels du harnais, variables de dépôt, gabarits de PR et formulaires d'issue (épic / sous-tâche / bug),
  `CODEOWNERS` v0 (owner unique : @noesis-software-technologies), registre `config/feature_flags.yml` (vide)
  + module `apps/core/flags.py`, hooks `deploy/*.sh` (stubs), `harness.mk`.
- CI adaptée au dépôt : deps sans `faster-whisper` (comme `ci.yml`), pas de Postgres/Redis (dev = SQLite +
  InMemoryChannelLayer), lint ruff **scopé v0** aux fichiers du harnais (le dépôt a ~150 findings : PR
  d'autofix dédiée avant d'élargir `ruff check .`).

## Ce qui reste à toi (dans l'ordre, ~10 min)

1. Merger la PR `chore/release-harness` (CI verte exigée).
2. Brancher le context processor (1 ligne, hors PR pour ne pas toucher `config/` sans toi) :
   `config/settings/base.py` → `TEMPLATES[0]["OPTIONS"]["context_processors"] += ["apps.core.flags.feature_flags"]`
   et `pyyaml` dans `requirements.txt` s'il n'y est pas.
3. Environnements : Settings → Environments → `staging` et `production` (Required reviewers : toi).
4. Quand les trois équipes ont pris le pli (quelques PR conformes) : `scripts/gh/30-protect-branches.sh`
   — c'est LE geste qui rend les gates bloquantes. Pas avant.
5. Optionnel : `gh secret set SLACK_WEBHOOK_URL` ; plus tard `scripts/gh/00-bootstrap-teams.sh` +
   `make -f harness.mk init` si tu crées de vraies équipes GitHub.

## Premier épic recommandé

Le **fork produit missions ↔ modes** (décision PO en attente, cf. ROADMAP) est le candidat idéal : c'est une
décision de cadrage → formulaire « Épic (PM) » (North Star, guardrails, non-goals, tier 2), label
`epic:approved`, puis `scripts/gh/10-new-epic.sh --epic <n> --slug cockpit-modes --pod spacelabs --task …`
et chaque équipe IA prend une sous-tâche (protocole : `AI_TEAMS.md` §2).

## Migration des habitudes actuelles

Les branches historiques `feat/*` finissent leur vie normalement (checks consultatifs). Tout travail
**nouveau** part d'un épic et suit la convention `sub-feature/<epic>/<task>` → `feature/<epic>` → `main`.
Les zips de sprint livrés en chat restent le rituel de la session ; **la vérité du code est le dépôt**.
